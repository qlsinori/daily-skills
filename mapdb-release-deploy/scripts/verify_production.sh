#!/usr/bin/env bash
set -euo pipefail

TAG=${1:?usage: verify_production.sh vX.Y.Z}
HOST=${MAPDB_DEPLOY_HOST:-10.136.29.157}
USER_NAME=${MAPDB_DEPLOY_USER:-xchu}
RELEASE_REPO=${MAPDB_RELEASE_REPO:-/home/xchu/my_git/memory_module}
if ! [[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "[mapdb-production] invalid release tag: $TAG" >&2
    exit 2
fi
REVISION=$(git -C "$RELEASE_REPO" rev-list -n 1 "$TAG")
if ! [[ "$REVISION" =~ ^[0-9a-f]{40}$ ]]; then
    echo "[mapdb-production] cannot resolve release revision: $TAG" >&2
    exit 2
fi
ssh -o BatchMode=yes -o ConnectTimeout=10 "$USER_NAME@$HOST" "
set -eu
actual_image=\$(docker inspect semantic-mapdb --format '{{.Config.Image}}')
actual_tag=\$(docker inspect semantic-mapdb --format '{{index .Config.Labels \"io.x2robot.mapdb.release-tag\"}}')
actual_revision=\$(docker inspect semantic-mapdb --format '{{index .Config.Labels \"io.x2robot.mapdb.release-revision\"}}')
actual_channel=\$(docker inspect semantic-mapdb --format '{{index .Config.Labels \"io.x2robot.mapdb.deployment-channel\"}}')
runtime_source=\$(docker inspect semantic-mapdb --format '{{range .Mounts}}{{if eq .Destination \"/home/xchu/hydra_ws/hydra_custom\"}}{{.Source}} {{.RW}}{{end}}{{end}}')
case \"\$actual_image\" in semantic-mapdb:v[0-9]*.[0-9]*.[0-9]*) ;; *) exit 1 ;; esac
[ \"\$actual_tag\" = '$TAG' ]
[ \"\$actual_revision\" = '$REVISION' ]
[ \"\$actual_channel\" = tag-pipeline ]
case \"\$runtime_source\" in */releases/$TAG-${REVISION:0:12}/hydra_custom\ false) ;; *) exit 1 ;; esac
[ \"\$(docker inspect semantic-mapdb --format '{{.State.Health.Status}}')\" = healthy ]
printf 'image=%s release_tag=%s release_revision=%s channel=%s runtime=read-only\\n' \
    \"\$actual_image\" \"\$actual_tag\" \"\$actual_revision\" \"\$actual_channel\"
curl -fsS --max-time 10 http://127.0.0.1:8899/api/health
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
"
curl -fsS --max-time 10 "http://$HOST:8899/api/health"
echo
echo "[mapdb-production] verified semantic-mapdb:$TAG"
