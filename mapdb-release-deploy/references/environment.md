# Semantic MapDB release environment

## Paths

- Active implementation: `/home/xchu/hydra_ws/hydra_custom`
- Workspace root: `/home/xchu/hydra_ws`
- Release repository: `/home/xchu/my_git/memory_module`
- Published source subtree: `/home/xchu/my_git/memory_module/semantic_mapping/hydra_custom`
- Docker deployment: `/home/xchu/my_git/memory_module/semantic_mapping/docker/mapdb`
- Single changelog: `/home/xchu/my_git/memory_module/semantic_mapping/CHANGELOG.md`
- Hydra Python: `/home/xchu/.miniconda3/envs/hydra_noetic/bin/python`

## GitLab and deployment

- GitLab project: `echo/memory_module`
- API base: `http://10.100.10.12/api/v4`
- Token file: `~/.config/gitlab/mapdb_api_token` (mode 600; never print)
- Production SSH: `xchu@10.136.29.157`
- Container: `semantic-mapdb`
- Service: `http://10.136.29.157:8899`
- Persistent data: `/srv/semantic-mapdb/data`

The legacy single-GPU host is independently retained at
`sergio@10.136.27.172` with service URL `http://10.136.27.172:8899`. It is
pinned to `v2.66.57`; do not send the dual-GPU tag deployment to this host.

The `.gitlab-ci.yml` tag rule deploys tags matching `vMAJOR.MINOR.PATCH`. The deploy job waits for active jobs, verifies dependency-image reuse on the target (building only when required), activates an immutable code release with its verified image, checks health, and rolls back on failure. The code release tag and dependency image tag can differ.

## Dedicated CI runner

- Production CI tag: `mapdb-dual5090` (protected project runner; no untagged jobs).
- User service: `mapdb-gitlab-runner.service` on the production host.
- Install helper: `semantic_mapping/docker/mapdb/install_runner.sh`.
- Runner config is private host state, never versioned; use a placeholder such as `<RUNNER_AUTH_TOKEN>` in examples.
- Inspect manager timestamps together with actual service state and sanitized job/request logs; both online and contacted_at can be delayed. Timestamp age alone is not proof that the runner stopped.
- Versioned skill snapshot: `semantic_mapping/docker/mapdb/release_skill/`.

- Full deployment lock: `$HOME/.local/share/mapdb-runner/deploy.lock` on the production runner host, acquired by `run_deploy_locked.sh`. Retired GitLab resource-group jobs must not be retried.
