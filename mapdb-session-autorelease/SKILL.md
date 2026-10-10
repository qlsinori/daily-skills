---
name: mapdb-session-autorelease
description: 为 memory_module 项目启用可跨会话持续的修改后发布规范：测试、同步最新 develop、提交、Git SSH 推新版本 tag、等待 CI 并核验 157；用户首次调用时安装持久规则，用户明确关闭时撤销。
---

# MapDB 持续发布规范

## 启用与持续范围

用户明确调用本 skill 即授权：在 `gitlab.x2robot.com/echo/memory_module` 的开发任务中，每批已完成的代码修改都按本规范提交和发布到 `10.136.29.157:8899`，直到用户明确关闭。一批指一个可验证、完整的功能或修复；不为每次文件保存或未完成的中间编辑发版。

1. 核实当前仓库 `origin` 与项目匹配；当前目录是 worktree 父目录时先找到用户正在使用的仓库，不猜测其他项目。
2. 首次显式调用执行 `scripts/persistent_policy.py enable --repo <仓库绝对路径>`。脚本只在当前 Codex profile 的有效全局 `AGENTS.md` / `AGENTS.override.md` 中维护本项目限定的规则块，保留原文并备份。使用全局限定规则是为了覆盖同一仓库的多个 worktree 和之后的新会话。
3. 若本 skill 仅被自动发现而用户尚未明确调用，检查 `status`；未启用时不能自行安装规则或认定获得持续发布授权。
4. 启用后，在本会话继续、压缩恢复和同一 Codex profile 的新会话中持续遵守，不反复询问是否提交、打 tag 或发布。压缩摘要保留启用状态、仓库、最近 tag/提交、未完成的流水线和验证项。
5. 用户说“这次只在本地”或“先不要发布”：本次任务按其最新要求处理，保留持续规则。用户说“关闭/取消持续发布”：执行 `scripts/persistent_policy.py disable`，只移除本 skill 的规则块。创建 skill 本身不等于已经调用启用。

只读排查且没有代码变更时不发版。该授权不包含删除生产数据、取消同事任务、修改独立 Viewer、向机器人部署、立即发群消息或改变访问权限。更具体的当前用户要求优先。

## 每批代码修改的交付闭环

- 先阅读项目实际 `AGENTS.md` 和 `mapdb-project-development`，核实分支、脏工作区、线上版本及原始问题；保存同事改动和用户数据。
- 做最小修复，运行覆盖真实功能、持久化、恢复和失败路径的相关测试；按项目要求完成独立审查。只读测试使用隔离数据，不能为测试删除地图或打断真实工作。
- 获取最新 `origin/develop` 与远端版本 tags；保留同事提交，解决明确冲突，必要时使用隔离的干净 develop worktree。最终发布来自最新 develop，不新建每次发布的 release 分支，不强推或重置别人改动。
- 读取 `mapdb-release-deploy` 的安全门禁与当前 CI 脚本，完成所需部署校验、镜像复用判断、runner 和并发发布检查。使用新 PATCH 版本，维护唯一中英文 CHANGELOG 和中文通知摘要。
- **本用户指定 Git SSH 发布**：按 [Git SSH 发布方法](references/git-ssh-release.md) 推送 develop 与新的 annotated tag，触发现有受保护 tag 流水线。没有 `~/.config/gitlab/mapdb_api_token` 不是 SSH 发布的阻塞，不把 release helper 的 `/user` 要求变成必须提供 token 的要求。不修改或绕过 CI 门禁。
- 观察必需 job 的实际结果；无 API token 时通过 157 的 runner 日志、发布目录、容器元数据和服务 API 获取证据。只成功 push tag 不等于部署成功；日志无法证明的 pipeline 总状态明确写“未核验”。
- 流水线等待真实活跃任务时继续检查进度，保留部署锁和 idle 门禁，不取消同事任务、不反复加 tag 绕过等待。确实无法推进时说明当前 job、等待原因和仍在服务的版本，不能宣称已发布上线。
- 部署完成后核对 tag、提交、容器健康、`/api/health`、`/api/version`、两张 GPU 和受影响页面/API；修复失败时从具体失败门禁恢复。只有通过生产验证才能报告“已上线”。

## 结束报告

简要给出：改动、实际测试结果、提交 SHA、新 tag、CI job/结果、157 实际版本与健康、关键功能验证和未完成项。已启用规则时，不以“需要我提交吗/要打 tag 吗”结束。

持久发现机制遵循 [官方 AGENTS.md 文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。新 profile、另一台机器或覆盖此规则的项目指令不会自动继承；遇到这些情况如实说明并重新按用户授权安装。
