#!/usr/bin/env python3
"""End-to-end smoke test for annotate_pdf.py."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "annotate_pdf.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="zotero-annotate-test-") as temp:
        work = Path(temp)
        source = work / "source.pdf"
        output = work / "annotated.pdf"
        plan = work / "plan.json"
        report = work / "report.json"

        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), "Core contribution improves accuracy by 12.5 percent.", fontsize=12)
        page.insert_text((72, 140), "A key limitation is the small sample size.", fontsize=12)
        doc.save(source)
        doc.close()
        original_hash = sha256(source)

        plan.write_text(json.dumps([
            {
                "quote": "improves accuracy by 12.5 percent",
                "comment": "证据：准确率提升 12.5%，需结合基线与测试集规模解读。",
                "category": "evidence",
                "page": 1,
            },
            {
                "quote": "small sample size",
                "comment": "局限：样本量较小，可能削弱结论的外部有效性。",
                "category": "limitation",
                "page": 1,
            },
        ], ensure_ascii=False), encoding="utf-8")

        run = subprocess.run([
            sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output),
            "--annotations", str(plan), "--report", str(report),
        ], capture_output=True, text=True, encoding="utf-8", check=False)
        assert run.returncode == 0, run.stderr or run.stdout
        assert sha256(source) == original_hash
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["planned"] == data["written"] == 2
        assert data["unmatched"] == data["ambiguous"] == 0

        reopened = fitz.open(output)
        try:
            properties = [
                (annotation.info["content"], annotation.type[1], annotation.opacity)
                for annotation in (reopened[0].annots() or [])
            ]
            assert len(properties) == 2
            assert "准确率提升 12.5%" in properties[0][0]
            assert "外部有效性" in properties[1][0]
            assert all(annotation_type == "Highlight" for _, annotation_type, _ in properties)
            assert all(abs(opacity - 0.38) < 0.01 for _, _, opacity in properties)
            pix = reopened[0].get_pixmap(annots=True, matrix=fitz.Matrix(1, 1))
            assert len(pix.samples) > 0
        finally:
            reopened.close()

        missing_plan = work / "missing.json"
        missing_output = work / "should-not-exist.pdf"
        missing_plan.write_text(json.dumps([{
            "quote": "text that is absent",
            "comment": "不应静默成功。",
            "category": "question",
        }], ensure_ascii=False), encoding="utf-8")
        failed = subprocess.run([
            sys.executable, str(SCRIPT), "--input", str(source), "--output", str(missing_output),
            "--annotations", str(missing_plan),
        ], capture_output=True, text=True, encoding="utf-8", check=False)
        assert failed.returncode == 2
        assert not missing_output.exists()

    print("PASS: PDF annotations, Chinese comments, styling, source integrity, and failure handling")


if __name__ == "__main__":
    main()
