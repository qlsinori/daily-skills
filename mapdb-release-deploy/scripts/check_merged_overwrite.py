#!/usr/bin/env python3
"""Refuse a release sync that would revert changes already on develop.

release_mapdb.sh copies explicit paths from the active workspace (not a Git
checkout) over the release repository with rsync (no --delete). Merge requests
reach develop independently, so the active copy of a file may predate them.

For every file under the requested paths whose active copy differs from HEAD:
  * the active copy must contain HEAD's changes: the file's historical version
    on develop closest to the active copy is taken as its base, and a
    three-way merge (base -> HEAD applied to the active copy) must leave the
    active copy unchanged;
  * a file deleted on develop must not be recreated by the sync.

Deliberate reverts are allowed only by listing the files in
MAPDB_RELEASE_ACCEPT_REVERT (comma separated, relative to hydra_custom)
together with a non-empty MAPDB_RELEASE_REVERT_REASON.
"""

import argparse
import difflib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SUBTREE = "semantic_mapping/hydra_custom"
HISTORY_LIMIT = 200
BASE_CANDIDATES = 40  # recent versions considered as the active copy's base
DIFF_LINE_LIMIT = 20000  # larger files fall back to the newest older version
SKIP_PARTS = {"__pycache__", ".pytest_cache"}


def git(repo, *args, data=None, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], input=data, capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise SystemExit(
            "[mapdb-release] git " + " ".join(args[:3]) + " failed: "
            + result.stderr.decode(errors="replace").strip()
        )
    return result


def head_blobs(repo, pathspecs):
    """Map repository path -> blob id for regular files at HEAD."""
    literal = [":(literal)" + spec for spec in pathspecs]
    out = git(repo, "ls-tree", "-r", "-z", "HEAD", "--", *literal).stdout
    blobs = {}
    for record in filter(None, out.split(b"\0")):
        meta, path = record.split(b"\t", 1)
        mode, kind, sha = meta.split()
        if kind == b"blob":
            blobs[path.decode()] = sha.decode()
    return blobs


def active_files(active_root, relative_paths):
    for relative in relative_paths:
        source = active_root / relative
        candidates = [source] if source.is_file() else sorted(source.rglob("*"))
        for path in candidates:
            if not path.is_symlink() and not path.is_file():
                continue
            rel = path.relative_to(active_root)
            if SKIP_PARTS.intersection(rel.parts) or path.suffix == ".pyc":
                continue
            yield str(rel)


def hash_objects(active_root, relatives):
    """Blob ids as Git would store them; a symlink hashes its target text."""
    ids = {}
    regular = []
    for relative in relatives:
        path = active_root / relative
        if path.is_symlink():
            ids[relative] = subprocess.run(
                ["git", "hash-object", "--stdin"],
                input=os.readlink(path).encode(), capture_output=True, check=True,
            ).stdout.decode().strip()
        elif "\n" in relative:
            raise SystemExit(f"[mapdb-release] unsupported file name: {relative!r}")
        else:
            regular.append(relative)
    if regular:
        paths = "\n".join(str(active_root / r) for r in regular).encode() + b"\n"
        out = subprocess.run(
            ["git", "hash-object", "--no-filters", "--stdin-paths"], input=paths,
            capture_output=True, check=True,
        ).stdout.decode().split()
        ids.update(zip(regular, out))
    return ids


def blob(repo, sha):
    return git(repo, "cat-file", "blob", sha).stdout


def history(repo, repo_path):
    """Blob ids of the file in develop history, newest first (deduplicated)."""
    out = git(
        repo, "log", f"-{HISTORY_LIMIT}", "--format=%H", "HEAD", "--",
        ":(literal)" + repo_path,
    ).stdout.decode().split()
    seen, blobs = set(), []
    for commit in out:
        found = git(repo, "rev-parse", "--verify", "-q",
                    f"{commit}:{repo_path}", check=False)
        sha = found.stdout.decode().strip()
        if found.returncode == 0 and sha not in seen:
            seen.add(sha)
            blobs.append(sha)
    return blobs


def is_binary(data):
    return b"\0" in data[:8192]


def contains_head_changes(mine, base, theirs):
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, data in (("mine", mine), ("base", base), ("theirs", theirs)):
            path = Path(tmp) / name
            path.write_bytes(data)
            paths.append(str(path))
        result = subprocess.run(
            ["git", "merge-file", "-p", *paths], capture_output=True,
            check=False,
        )
    return result.returncode == 0 and result.stdout == mine


def closest(repo, versions, theirs_id, mine):
    """Older develop version nearest to mine (fewest differing lines).

    HEAD itself is excluded unless it is the only version: choosing HEAD as
    the base would hide a partial revert of HEAD's latest change.
    """
    candidates = ([sha for sha in versions if sha != theirs_id] or versions)[:BASE_CANDIDATES]
    text = mine.decode(errors="replace").splitlines()
    if len(text) > DIFF_LINE_LIMIT:
        return blob(repo, candidates[0])
    best, best_size = None, None
    for sha in candidates:
        data = blob(repo, sha)
        lines = data.decode(errors="replace").splitlines()
        if len(lines) > DIFF_LINE_LIMIT:
            continue
        matcher = difflib.SequenceMatcher(None, lines, text, autojunk=False)
        matched = sum(block.size for block in matcher.get_matching_blocks())
        size = len(lines) + len(text) - 2 * matched
        if best_size is None or size < best_size:
            best, best_size = data, size
    return best if best is not None else blob(repo, candidates[0])


def find_conflicts(active_root, repo, relative_paths):
    pathspecs = [f"{SUBTREE}/{p.rstrip('/')}" for p in relative_paths]
    heads = head_blobs(repo, pathspecs)
    relatives = sorted(set(active_files(active_root, relative_paths)))
    mine_ids = hash_objects(active_root, relatives)
    conflicts = []
    for relative in relatives:
        repo_path = f"{SUBTREE}/{relative}"
        theirs_id = heads.get(repo_path)
        if theirs_id == mine_ids[relative]:
            continue
        versions = history(repo, repo_path)
        if theirs_id is None:
            if versions:
                conflicts.append((relative, "deleted on develop; sync would restore it"))
            continue  # New file that never existed on develop.
        if mine_ids[relative] in versions:
            conflicts.append((relative, "active copy is an older develop version"))
            continue
        if (active_root / relative).is_symlink():
            conflicts.append((relative, "symlink target differs from develop"))
            continue
        mine = (active_root / relative).read_bytes()
        theirs = blob(repo, theirs_id)
        if is_binary(mine) or is_binary(theirs):
            conflicts.append((relative, "binary file differs from develop"))
            continue
        base = closest(repo, versions, theirs_id, mine)
        if not contains_head_changes(mine, base, theirs):
            conflicts.append((relative, "active copy lacks changes on develop"))
    return conflicts


def accepted_reverts():
    names = {
        item.strip() for item in
        os.environ.get("MAPDB_RELEASE_ACCEPT_REVERT", "").split(",")
        if item.strip()
    }
    reason = os.environ.get("MAPDB_RELEASE_REVERT_REASON", "").strip()
    if names and not reason:
        raise SystemExit(
            "[mapdb-release] MAPDB_RELEASE_ACCEPT_REVERT requires "
            "MAPDB_RELEASE_REVERT_REASON"
        )
    return names, reason


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-root", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--path", action="append", required=True, dest="paths")
    args = parser.parse_args()
    for relative in args.paths:
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise SystemExit(f"[mapdb-release] unsafe relative path: {relative}")
    if args.active_root.resolve() == (args.repo.resolve() / SUBTREE):
        # The release checkout is the active workspace: its working tree already holds
        # develop plus the reviewed edits, and the sync copies each file onto itself.
        print("[mapdb-release] active workspace is the release checkout itself; "
              "nothing is copied over develop")
        return
    accepted, reason = accepted_reverts()
    conflicts = find_conflicts(args.active_root.resolve(), args.repo, args.paths)
    blocking = [(p, r) for p, r in conflicts if p not in accepted]
    for path, why in conflicts:
        if path in accepted:
            print(f"[mapdb-release] accepted revert {path} ({why}): {reason}")
    if blocking:
        print("[mapdb-release] sync would revert changes already on develop:",
              file=sys.stderr)
        for path, why in blocking:
            print(f"  {path}: {why}", file=sys.stderr)
        print("[mapdb-release] merge origin/develop into the active workspace "
              "for these files and retest before releasing", file=sys.stderr)
        sys.exit(3)
    print("[mapdb-release] active workspace contains all develop changes "
          "for the requested paths")


if __name__ == "__main__":
    main()
