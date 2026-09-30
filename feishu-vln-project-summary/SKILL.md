---
name: feishu-vln-project-summary
description: Read a Feishu Wiki project tree and turn dated team records into evidence-based end-to-end VLN project summaries and resume-ready model/data paragraphs. Use when the user provides a Feishu Wiki URL and asks to search, filter, or summarize work; keep the Feishu source read-only.
---

# Feishu VLN project summary

将飞书知识库中的团队记录整理成可核查的端到端 VLN/VLA 项目材料。用户是项目负责人时，把团队页面中的已完成工作合并为项目级成果；不要把成员页面直接链接写入交付文件。

## 边界

- 飞书只读：不得创建、编辑、移动、删除节点或修改权限。只在本地写 Markdown 结果。
- 端到端范围优先包括模型训练、后训练、推理部署、仿真闭环、导航数据生成、标注、质检和自动评测。
- 过滤 agentic-VLN、Agent skill、memory、工具编排、纯语义地图/scene graph、AEB/AES 和与 VLN 无直接关系的传统导航内容；除非用户明确要求保留。
- 区分“已完成”“正在进行”“计划/调研”和“仅背景”。只有原文明确完成的事项才能写成简历成果；计划不能改写成完成结果。

## 工作流

1. 使用已授权的 `lark-cli`，优先 `--as user`。飞书 Wiki URL 走 `lark-wiki`/`lark-doc`，不要用普通网页抓取替代飞书读取。
2. 先解析根节点：

   ```powershell
   lark-cli wiki +node-get --node-token '<wiki-url>' --as user --format json
   ```

   从结果取得真实 `space_id`、`node_token` 和文档对象 token。

3. 用 `wiki +node-list --page-all --page-limit 0` 列出根节点，并递归读取所有 `has_child=true` 的子节点。不能只读第一页或只读一个成员页面。
4. 对每个可读文档使用 `lark-cli docs +fetch --doc <doc-url-or-token> --doc-format markdown --detail simple`。保留页面标题、原文日期和能证明结论的原句；图片只作辅助证据，不把图片描述当成完成记录。
5. 建立筛选表，至少包含：原始页面、原文日期、工作类型（模型/数据/评测）、明确完成的证据、简历可用表述、排除理由。相同工作跨页面出现时合并，但保留所有来源页面和日期范围。
6. 输出本地 Markdown，建议结构：

   - 数据源与读取范围（只放用户提供的根 Wiki URL）；
   - 模型训练与部署项目；
   - 数据生成、监督与评测项目；
   - 原始来源与时间表；
   - 排除项及理由；
   - 最后给出两段可直接放进简历的文字，分别对应“模型”和“数据”。

7. 交付前检查：没有成员页直链、没有把计划写成成果、没有把 agentic-VLN 写成端到端 VLN、每个关键数字都有来源页面和日期。若证据不足，使用“参与/支持/记录显示”而不是编造指标。

## 简历转写规则

- 每条经历按“负责什么 → 用什么方法 → 产出什么数据/模型 → 如何验证或部署”组织，优先写清楚动作之间的关系，不把页面里的关键词原样串接。
- 面向外部读者时，将团队内部平台名、服务名和临时代号翻译成“仿真导航数据生成”“多模态监督”“闭环评测”等能力描述；Qwen、InternNav、LoRA、PPO 等能帮助读者判断技术栈的名称可以保留。
- 最终简历段落不应出现孤立的占位符、导出残留或无法解释的内部字符串；每个指标和技术名都要能回指到原始记录。

## 结果文件

用户要求“写一个 md 文件”时，默认在当前项目工作区生成或更新 `端到端VLN项目筛选与简历素材.md`。不上传该 Markdown 到 Overleaf，除非用户明确要求；它是分析底稿，不是简历源文件。
