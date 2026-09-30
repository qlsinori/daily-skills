#!/usr/bin/env python3
"""Publish only the reviewed, credential-free release skill files."""

import argparse
import os
from pathlib import Path
import re
import shutil

FILES = (
    "SKILL.md",
    "references/environment.md",
    "scripts/release_mapdb.sh",
    "scripts/wait_pipeline.sh",
    "scripts/verify_production.sh",
    "scripts/sync_release_skill.py",
)
SECRET_PATTERN = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"
    r"|\b(?:glpat|glrt)-[A-Za-z0-9_-]{16,}"
    r"|\bAKIA[A-Z0-9]{16}\b"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = args.repo.resolve() / "semantic_mapping/docker/mapdb/release_skill"
    contents = {}
    for relative in FILES:
        path = source / relative
        if path.is_symlink():
            raise SystemExit(f"Refusing skill symlink: {relative}")
        data = path.read_bytes()
        if SECRET_PATTERN.search(data.decode("utf-8")):
            raise SystemExit(
                f"Remove embedded credentials before syncing: {relative}"
            )
        contents[relative] = data
    for relative, data in contents.items():
        destination = target / relative
        if destination.is_symlink():
            raise SystemExit(f"Refusing repository symlink: {relative}")
        if args.check:
            if not destination.is_file() or destination.read_bytes() != data:
                raise SystemExit(f"Release skill snapshot differs: {relative}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.resolve() != (source / relative).resolve():
                shutil.copyfile(source / relative, destination)
                os.chmod(
                    destination, (source / relative).stat().st_mode & 0o777
                )
    print(
        "Release skill snapshot verified"
        if args.check
        else "Release skill snapshot synchronized"
    )


if __name__ == "__main__":
    main()
