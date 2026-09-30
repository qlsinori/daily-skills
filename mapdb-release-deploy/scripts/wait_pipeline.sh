#!/usr/bin/env bash
set -euo pipefail

TAG=${1:?usage: wait_pipeline.sh vX.Y.Z}
API=${MAPDB_GITLAB_API:-http://10.100.10.12/api/v4}
PROJECT=${MAPDB_GITLAB_PROJECT:-echo%2Fmemory_module}
TOKEN_FILE=${MAPDB_GITLAB_TOKEN_FILE:-$HOME/.config/gitlab/mapdb_api_token}
TIMEOUT_S=${MAPDB_PIPELINE_TIMEOUT_S:-21600}
if [ ! -r "$TOKEN_FILE" ]; then
    echo "[mapdb-pipeline] token file is missing or unreadable: $TOKEN_FILE" >&2
    exit 2
fi
deadline=$((SECONDS + TIMEOUT_S))
pipeline_id=""
while [ "$SECONDS" -lt "$deadline" ]; do
    payload=$(printf 'header = "PRIVATE-TOKEN: %s"\n' "$(<"$TOKEN_FILE")" \
        | curl -fsS --config - \
            "$API/projects/$PROJECT/pipelines?ref=$TAG&per_page=1")
    parsed=$(printf '%s' "$payload" | python3 -c 'import json,sys; rows=json.load(sys.stdin); print((str(rows[0]["id"])+" "+rows[0]["status"]) if rows else "")')
    if [ -z "$parsed" ]; then
        echo "[mapdb-pipeline] waiting for tag pipeline: $TAG"
        sleep 5
        continue
    fi
    pipeline_id=${parsed%% *}
    status=${parsed#* }
    echo "[mapdb-pipeline] pipeline=$pipeline_id status=$status"
    case "$status" in
        success) exit 0 ;;
        failed|canceled|skipped|manual) exit 3 ;;
    esac
    sleep 15
done
echo "[mapdb-pipeline] timeout waiting for $TAG (pipeline ${pipeline_id:-unknown})" >&2
exit 4
