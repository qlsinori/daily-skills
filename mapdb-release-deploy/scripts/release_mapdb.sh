#!/usr/bin/env bash
set -euo pipefail

ACTIVE_ROOT=${MAPDB_ACTIVE_ROOT:-/home/xchu/hydra_ws/hydra_custom}
WORKSPACE=${MAPDB_WORKSPACE:-/home/xchu/hydra_ws}
RELEASE_REPO=${MAPDB_RELEASE_REPO:-/home/xchu/my_git/memory_module}
HYDRA_PY=${HYDRA_PY:-/home/xchu/.miniconda3/envs/hydra_noetic/bin/python}
TAG="auto"
MESSAGE=""
EXECUTE=0
PATHS=()
TEST_PATHS=()

usage() {
    echo "usage: $0 [--tag auto|vX.Y.Z] --message TEXT --path RELATIVE_PATH [--path ...] [--test-path tests/FILE] [--execute]" >&2
}
while [ "$#" -gt 0 ]; do
    case "$1" in
        --tag) TAG=${2:-}; shift 2 ;;
        --message) MESSAGE=${2:-}; shift 2 ;;
        --path) PATHS+=("${2:-}"); shift 2 ;;
        --test-path) TEST_PATHS+=("${2:-}"); shift 2 ;;
        --execute) EXECUTE=1; shift ;;
        *) usage; exit 2 ;;
    esac
done
if { [ "$TAG" != "auto" ] && ! [[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; } \
        || [ -z "$MESSAGE" ] || [ "${#PATHS[@]}" -eq 0 ]; then
    usage
    exit 2
fi
for path in "$ACTIVE_ROOT" "$RELEASE_REPO/.git" "$HYDRA_PY"; do
    if [ ! -e "$path" ]; then
        echo "[mapdb-release] missing required path: $path" >&2
        exit 2
    fi
done
branch=$(git -C "$RELEASE_REPO" branch --show-current)
if [ "$branch" != "develop" ]; then
    echo "[mapdb-release] releases must be committed from develop, current branch: ${branch:-detached}" >&2
    exit 2
fi
remote_develop=$(git -C "$RELEASE_REPO" ls-remote --heads origin refs/heads/develop)
if [ -n "$remote_develop" ]; then
    remote_develop_sha=${remote_develop%%[[:space:]]*}
    local_sha=$(git -C "$RELEASE_REPO" rev-parse HEAD)
    if [ "$local_sha" != "$remote_develop_sha" ]; then
        echo "[mapdb-release] develop is not synchronized with origin/develop" >&2
        exit 2
    fi
fi
if [ "$TAG" = "auto" ]; then
    latest_tag=$(
        git -C "$RELEASE_REPO" ls-remote --tags --refs origin 'refs/tags/v*' \
            | awk '$2 ~ /^refs\/tags\/v[0-9]+\.[0-9]+\.[0-9]+$/ {
                sub("refs/tags/", "", $2); print $2
            }' \
            | sort -V \
            | tail -n 1
    )
    if [ -z "$latest_tag" ]; then
        TAG="v0.0.1"
    elif [[ "$latest_tag" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        TAG="v${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.$((BASH_REMATCH[3] + 1))"
    else
        echo "[mapdb-release] cannot parse latest SemVer tag: $latest_tag" >&2
        exit 2
    fi
    echo "[mapdb-release] selected automatic patch tag: $TAG"
fi
if git -C "$RELEASE_REPO" rev-parse "$TAG" >/dev/null 2>&1 \
        || [ -n "$(git -C "$RELEASE_REPO" ls-remote --tags --refs origin "refs/tags/$TAG")" ]; then
    echo "[mapdb-release] tag already exists: $TAG" >&2
    exit 2
fi

# Validate public notification copy before lengthy tests or any publication.
"$HYDRA_PY" "$ACTIVE_ROOT/scripts/notify_mapdb_feishu.py" validate \
    --tag "$TAG" --changelog "$RELEASE_REPO/semantic_mapping/CHANGELOG.md"

# Resolve attribution from the authenticated GitLab account, never the OS user.
"$HYDRA_PY" - "$RELEASE_REPO" "$TAG" <<'PY_ATTRIBUTION'
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

root, tag = sys.argv[1:]
api = os.environ.get("MAPDB_GITLAB_API", "http://10.100.10.12/api/v4")
token_path = Path(os.environ.get("MAPDB_GITLAB_TOKEN_FILE", str(Path.home() / ".config/gitlab/mapdb_api_token")))
request = urllib.request.Request(api.rstrip("/") + "/user", headers={"PRIVATE-TOKEN": token_path.read_text().strip()})
with urllib.request.urlopen(request, timeout=15) as response:
    username = json.load(response)["username"]
if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
    raise SystemExit("Invalid GitLab contributor username")
path = Path(root) / "semantic_mapping/CHANGELOG.md"
text = path.read_text()
pattern = re.compile(r"^(## " + re.escape(tag[1:]) + r" - [^\n]+)$", re.MULTILINE)
match = pattern.search(text)
if not match:
    raise SystemExit("Missing changelog heading for " + tag)
entry = text[match.end():].split("\n## ", 1)[0]
for label in ("中文：", "English:"):
    section = re.search(r"^" + re.escape(label) + r"\s*\n\s*- \S", entry, re.MULTILINE)
    if not section:
        raise SystemExit("Missing readable changelog section: " + label)
heading = match[0]
if "@" + username not in heading.split():
    text = text[:match.start()] + heading + " @" + username + text[match.end():]
    path.write_text(text)
print("[mapdb-release] authenticated GitLab contributor: @" + username)
PY_ATTRIBUTION

echo "[mapdb-release] active-source syntax"
bash -n "$ACTIVE_ROOT/run_qiyu_mapdb_sparse_rooms.sh"
"$HYDRA_PY" -m py_compile \
    "$ACTIVE_ROOT/mapdb/serve_map_db.py" \
    "$ACTIVE_ROOT/mapdb/visual_evidence.py" \
    "$ACTIVE_ROOT/mapdb/postprocess_edit.py" \
    "$ACTIVE_ROOT/mapdb/interiorgs_evaluation.py" \
    "$ACTIVE_ROOT/mapdb/service_worker.py" \
    "$ACTIVE_ROOT/mapdb/service/app.py" \
    "$ACTIVE_ROOT/mapdb/service/bug_reports.py" \
    "$ACTIVE_ROOT/mapdb/service/job_routes.py" \
    "$ACTIVE_ROOT/mapdb/service/config.py"
if [ "${#TEST_PATHS[@]}" -gt 0 ]; then
    selected_tests=()
    for test_path in "${TEST_PATHS[@]}"; do
        if [[ "$test_path" != tests/test_*.py || "$test_path" == *".."* ]] || [ ! -f "$ACTIVE_ROOT/$test_path" ]; then
            echo "[mapdb-release] invalid test path: $test_path" >&2
            exit 2
        fi
        selected_tests+=("$ACTIVE_ROOT/$test_path")
    done
    echo "[mapdb-release] reviewed functional regressions: ${TEST_PATHS[*]}"
    (cd "$WORKSPACE" && env -u PYTHONPATH "$HYDRA_PY" -m pytest -q "${selected_tests[@]}")
else
echo "[mapdb-release] service regressions"
(cd "$WORKSPACE" && "$HYDRA_PY" -m unittest hydra_custom.tests.test_mapdb_service)
echo "[mapdb-release] editor regressions"
(cd "$WORKSPACE" && "$HYDRA_PY" -m unittest hydra_custom.tests.test_mapdb_editor)

if [ -f "$ACTIVE_ROOT/tests/test_viewer_operation_store.py" ]; then
    echo "[mapdb-release] incremental workspace, browser and migration regressions"
    (cd "$WORKSPACE" && "$HYDRA_PY" -m pytest -q \
        "$ACTIVE_ROOT"/tests/test_viewer*.py \
        "$ACTIVE_ROOT"/tests/test_manage_viewer_workspaces.py)
fi

fi

echo "[mapdb-release] synchronizing explicit hydra_custom paths"
for relative in "${PATHS[@]}"; do
    if [[ "$relative" = /* || "$relative" == *".."* ]]; then
        echo "[mapdb-release] unsafe relative path: $relative" >&2
        exit 2
    fi
    source_path="$ACTIVE_ROOT/$relative"
    target_path="$RELEASE_REPO/semantic_mapping/hydra_custom/$relative"
    if [ ! -e "$source_path" ]; then
        echo "[mapdb-release] requested source path does not exist: $relative" >&2
        exit 2
    fi
    mkdir -p "$(dirname "$target_path")"
    rsync -a --exclude '__pycache__/' --exclude '*.pyc' --exclude '.pytest_cache/' \
        "$source_path" "$target_path"
done

echo "[mapdb-release] synchronizing reviewed release skill"
"$HYDRA_PY" "$(dirname "$0")/sync_release_skill.py" --repo "$RELEASE_REPO"

echo "[mapdb-release] release-repository validation"
bash -n "$RELEASE_REPO"/semantic_mapping/docker/mapdb/*.sh
for validator in validate_code_release verify_installed_dependencies dependency_image_candidates; do
    "$HYDRA_PY" "$RELEASE_REPO/semantic_mapping/docker/mapdb/$validator.py" --self-test
done
"$HYDRA_PY" -m unittest discover -s "$RELEASE_REPO/semantic_mapping/docker/mapdb" \
    -p 'test_*.py'
for validator in validate_docker_cache_layout validate_runtime_recovery; do
    "$HYDRA_PY" "$RELEASE_REPO/semantic_mapping/docker/mapdb/$validator.py"
done
# Every shipped script's sibling-module imports must resolve inside the
# release tree; a missing sibling (e.g. instance_depth_refinement in v2.63.x)
# crashes the container pipeline at import time.
"$HYDRA_PY" - "$ACTIVE_ROOT" "$RELEASE_REPO/semantic_mapping/hydra_custom" <<'PYEOF'
import ast, sys
from pathlib import Path
active_scripts = Path(sys.argv[1]) / "scripts"
release_scripts = Path(sys.argv[2]) / "scripts"
missing = []
for shipped in sorted(release_scripts.glob("*.py")):
    try:
        tree = ast.parse(shipped.read_text())
    except SyntaxError as exc:
        print(f"[mapdb-release] syntax error in shipped script {shipped.name}: {exc}",
              file=sys.stderr)
        sys.exit(2)
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods = [node.module.split(".")[0]]
        for mod in mods:
            if (active_scripts / f"{mod}.py").exists() and \
                    not (release_scripts / f"{mod}.py").exists():
                missing.append(f"{shipped.name} -> {mod}.py")
if missing:
    print("[mapdb-release] shipped scripts import sibling modules missing from "
          "the release tree:", file=sys.stderr)
    for entry in sorted(set(missing)):
        print(f"  {entry}", file=sys.stderr)
    sys.exit(2)
print("[mapdb-release] shipped-script sibling imports resolve in release tree")
PYEOF
git -C "$RELEASE_REPO" diff --check
git -C "$RELEASE_REPO" status --short
git -C "$RELEASE_REPO" diff --stat
if [ "$EXECUTE" != "1" ]; then
    echo "[mapdb-release] validation complete; rerun with --execute to commit, tag and push"
    exit 0
fi
if git -C "$RELEASE_REPO" diff --quiet && \
        git -C "$RELEASE_REPO" diff --cached --quiet && \
        [ -z "$(git -C "$RELEASE_REPO" ls-files --others --exclude-standard)" ]; then
    echo "[mapdb-release] no release changes to commit" >&2
    exit 2
fi

git -C "$RELEASE_REPO" add .
# The release checkout may locally ignore Markdown; these reviewed skill files
# are explicit publication inputs, not generated notes.
git -C "$RELEASE_REPO" add -f -- \
    semantic_mapping/docker/mapdb/release_skill/SKILL.md \
    semantic_mapping/docker/mapdb/release_skill/references/environment.md
git -C "$RELEASE_REPO" commit -m "$MESSAGE"
git -C "$RELEASE_REPO" tag -a "$TAG" -m "$MESSAGE"
git -C "$RELEASE_REPO" push origin develop
git -C "$RELEASE_REPO" push origin "$TAG"
echo "[mapdb-release] published $TAG at $(git -C "$RELEASE_REPO" rev-parse --short HEAD)"
