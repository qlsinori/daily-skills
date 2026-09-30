# daily-skills

个人维护的 Codex skills 集合，覆盖代码阅读、飞书内容整理、工作汇报、图文 SOP 和简历编辑。

## Skills

| Skill | 用途 |
| --- | --- |
| [`assist-code-reading`](assist-code-reading/) | 从代码入口追踪训练与推理链路，生成中文代码阅读材料 |
| [`feishu-vln-project-summary`](feishu-vln-project-summary/) | 从飞书 Wiki 整理 VLN 项目经历和简历素材 |
| [`karpathy-guidelines`](karpathy-guidelines/) | 编写、审查和重构代码时的简洁性与验证准则 |
| [`lark-semantic-map-issue-extractor`](lark-semantic-map-issue-extractor/) | 从飞书测试群提取语义地图问题并增量更新文档 |
| [`mapdb-project-development`](mapdb-project-development/) | MapDB 项目开发、数据保护、隔离测试与交付约束 |
| [`mapdb-release-deploy`](mapdb-release-deploy/) | MapDB 版本发布、GitLab 标记、流水线和部署验证 |
| [`report`](report/) | 汇总指定时间范围内的 Codex 工作记录 |
| [`resume-edit-overleaf`](resume-edit-overleaf/) | 修改、编译并检查 LaTeX 简历，按要求推送到 Overleaf |
| [`sop-documentation`](sop-documentation/) | 根据截图和操作流程生成图文 SOP，支持飞书 Markdown / Word |

## 使用

将需要的 skill 目录复制到 Codex skills 目录，或在对话中显式调用：

```text
$sop-documentation
```

每个 skill 的 `SKILL.md` 都包含适用范围和具体说明。

## 维护

```text
仓库：https://github.com/qlsinori/daily-skills
分支：main
```

新增或修改 skill 后，先运行 `quick_validate.py`，再提交并推送。
