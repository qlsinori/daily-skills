#!/usr/bin/env python3
"""Create a Zotero-readable PDF with tasteful Chinese highlight annotations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    raise SystemExit("缺少 PyMuPDF。请运行: python -m pip install PyMuPDF")


COLORS = {
    "contribution": (1.00, 0.84, 0.35),
    "method": (0.42, 0.72, 0.95),
    "evidence": (0.48, 0.82, 0.58),
    "limitation": (0.95, 0.52, 0.52),
    "question": (0.72, 0.57, 0.91),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--author", default="中文论文精读")
    return parser.parse_args()


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    args = parse_args()
    source = args.input.resolve()
    output = args.output.resolve()
    if source == output:
        fail("输出路径不能与源 PDF 相同。")
    if not source.is_file():
        fail(f"源 PDF 不存在: {source}")
    if output.exists():
        fail(f"拒绝覆盖已有文件: {output}")

    try:
        plan = json.loads(args.annotations.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"无法读取批注计划: {exc}")
    if not isinstance(plan, list):
        fail("批注计划必须是 JSON 数组。")

    document = fitz.open(source)
    results = []
    for index, item in enumerate(plan, 1):
        if not isinstance(item, dict):
            fail(f"第 {index} 条批注不是对象。")
        quote = str(item.get("quote", "")).strip()
        comment = str(item.get("comment", "")).strip()
        category = str(item.get("category", "")).strip()
        occurrence = item.get("occurrence", 1)
        page_hint = item.get("page")
        if not quote or not comment or category not in COLORS:
            fail(f"第 {index} 条必须含 quote、comment 和有效 category。")
        if not isinstance(occurrence, int) or occurrence < 1:
            fail(f"第 {index} 条 occurrence 必须是正整数。")
        if page_hint is not None and (not isinstance(page_hint, int) or not 1 <= page_hint <= len(document)):
            fail(f"第 {index} 条 page 超出范围。")

        pages = [page_hint - 1] if page_hint else range(len(document))
        matches = []
        for page_number in pages:
            for quads in document[page_number].search_for(quote, quads=True):
                matches.append((page_number, quads))

        status = "matched"
        if not matches:
            status = "unmatched"
        elif occurrence > len(matches):
            status = "unmatched"
        else:
            page_number, quad = matches[occurrence - 1]
            page = document[page_number]
            annot = page.add_highlight_annot(quad)
            annot.set_colors(stroke=COLORS[category])
            annot.set_opacity(0.38)
            annot.set_info(
                title=args.author,
                subject=f"精读批注 · {category}",
                content=comment,
            )
            annot.update()
            status = "ambiguous" if len(matches) > 1 and "occurrence" not in item else "matched"

        results.append({
            "index": index,
            "quote": quote,
            "category": category,
            "status": status,
            "matches": len(matches),
            "selected_page": matches[occurrence - 1][0] + 1 if matches and occurrence <= len(matches) else None,
        })

    failures = [r for r in results if r["status"] == "unmatched"]
    if failures:
        document.close()
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        document.save(output, garbage=4, deflate=True, clean=True)
        document.close()

    report = {
        "input": str(source),
        "output": str(output),
        "planned": len(results),
        "written": len(results) - len(failures),
        "unmatched": len(failures),
        "ambiguous": sum(r["status"] == "ambiguous" for r in results),
        "annotations": results,
    }
    report_text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report_text + "\n", encoding="utf-8")
    print(report_text)
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
