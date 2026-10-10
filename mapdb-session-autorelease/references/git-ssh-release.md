# Git SSH 发布方法

适用仓库：`gitlab.x2robot.com/echo/memory_module`。生产目标仅为 `xchu@10.136.29.157`，服务 `http://10.136.29.157:8899`。以下是本项目已验证的方法，不把历史 tag、runner ID、依赖镜像或本机路径视为当前事实。

## 发布前

1. 核实 `git status --short --branch`、`git remote -v`、当前 HEAD、生产 `/api/version`，获取远端 develop 和 tags。确认当前 CI 的 tag规则与 `mapdb-dual5090` runner 正常。远程检查使用现有 SSH 身份，不输出私钥、token 或生产 env。
2. 完成相关功能回归、项目要求的独立审查及实际 CI 部署校验。读当前 `.gitlab-ci.yml`；保留 shell syntax、code release allowlist、dependency reuse、cache layout、runtime recovery、通知摘要等门禁。复用已验证不可变依赖镜像；没有依赖变更时不重新安装 Torch/CUDA。
3. 保留当前改动并基于最新 develop 合并；脏工作区无法安全合并时创建隔离的干净 develop checkout，仅转移明确白名单的改动。不使用 `reset --hard`、强推或隐式 stash 清除他人工作。
4. 从远端 `vMAJOR.MINOR.PATCH` 的最大语义版本分配下一 PATCH；存在并发发布时协调一个发布人，推送前再核对 develop SHA 和 tag是否占用。API或持久格式不兼容时按用户要求决定版本及迁移，不掩饰为 PATCH。
5. 更新 `semantic_mapping/CHANGELOG.md`：中英文变化、PATCH理由、1–3 条简短中文通知摘要。校验实际通知 payload。没有 API发布者证据时不编造 `@用户名`；Git SSH greeting可记录为SSH认证证据，不能声称通过了 `/user`。CI提供的发布人元数据另按其真实来源记录。

## Git 推送

以下在核验过的发布 checkout 中执行，使用此次真实 tag 和提交消息替换示例。只 stage 审查过的文件；合并后再次检查完整暂存差异和必要回归。

```bash
git fetch origin --tags
git status --short --branch
git diff --check
git diff --cached --stat
# 明确列出本次文件，然后 commit；不要无差别 git add -A。
git add path/to/reviewed-file semantic_mapping/CHANGELOG.md
git commit -m '本次真实修改说明'
# 推送前重查 develop 是否有新提交，并确认所选 tag 不存在。
git ls-remote --heads origin refs/heads/develop
git ls-remote --tags origin refs/tags/vX.Y.Z
git tag -a vX.Y.Z -m '本次真实发布说明'
git push --atomic origin develop refs/tags/vX.Y.Z
```

- `.gitlab-ci.yml` 必须实际允许受保护的 `vX.Y.Z` tag运行验证和部署；不要依靠记忆认定已创建流水线。
- push被拒绝时检查真实错误：SSH认证、受保护tag权限、develop并发推进、网络或pre-receive。缺少API token不是SSH身份无权发布的证据。不改保护规则或强推。并发推进后合并最新 develop并复测；尚未发布的本地tag可重新分配，已推送tag绝不能移动或复用。
- 没有 token时不要调用要求该token的 `/user`、`wait_pipeline.sh` 或其发布wrapper，然后把预期失败报告成“不能部署”。改用下面的无token观察路径；如现有已授权token可用，API是可选的补充证据。

## 无 token 的 CI 与部署观察

```bash
ssh -o ClearAllForwardings=yes -o BatchMode=yes xchu@10.136.29.157 \
  'systemctl --user is-active mapdb-gitlab-runner.service'
ssh -o ClearAllForwardings=yes -o BatchMode=yes xchu@10.136.29.157 \
  'journalctl --user -u mapdb-gitlab-runner.service --since "10 min ago" --no-pager'
curl -fsS http://10.136.29.157:8899/api/version
curl -fsS http://10.136.29.157:8899/api/health
```

把接到的 job和此次tag/SHA实际 checkout对应起来，区分验证成功、部署正在执行、idle等待、部署成功和健康回退。确认所有必需job的最终状态，不能用一条验证成功代替整个流水线成功。必要时只读查看此次不可变发布目录和进程；不要输出runner配置、job token或生产环境变量。

激活后核对容器挂载的不可变代码tag/SHA和服务版本：依赖镜像可能沿用较早版本，单独报告它，不把镜像tag当代码版本。核实健康、GPU可见性及受影响的实际API/UI。长批次任务不必伪称全部完成，分别报告修复部署和任务运行状态。

真实工作使部署等待时保留原流水线继续等待；超时/失败后先修复具体原因，再按当前相同tag允许的正常重试流程处理，不能未核验就重试旧版本造成回退。
