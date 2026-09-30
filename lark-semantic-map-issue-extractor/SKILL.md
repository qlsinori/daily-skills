---
name: lark-semantic-map-issue-extractor
description: "语义地图建图问题提取：从飞书专项测试群提取原话、问题、原因、解决办法和截图，按时间水位去重并增量更新指定文档末尾的‘常见问题’，维护开头跳转链接；当用户需要整理语义地图建图问题时使用。"
metadata:
  requires:
    bins: ["lark-cli"]
    skills: ["lark-shared", "lark-im", "lark-doc", "lark-wiki"]
---

# 语义地图建图问题提取

> 前置条件：先阅读 [`../lark-shared/SKILL.md`](../lark-shared/SKILL.md)。读取群消息使用 [`../lark-im/SKILL.md`](../lark-im/SKILL.md)，读取/更新正文使用 [`../lark-doc/SKILL.md`](../lark-doc/SKILL.md)。

## 工作流

### 0. 每次先定位文末章节

默认目标文档为 `https://x2-robot.feishu.cn/wiki/SSsOwrwqei6uYEkfSZncoyfxnHb`；用户本次指定其他文档时以本次指定为准。直接编辑文档正文，不管理知识库节点。

每次调用先执行第 3 步的目录与章节读取，再读取水位和群消息。选择正文顺序中最后一个标题文本为“常见问题”的章节，并确认其正文边界；不得沿用上次的标题 block ID 或假设章节仍在原位置。用户已将该章节放在文末，不移动或重建它，不在前面新建同名章节。

文档开头维护一条“常见问题（点击跳转到文末）”链接，地址为 `文档基础URL#本次读取的常见问题标题block_id`。先读取开头：已有正确入口则不改，已有失效入口则局部更新，缺少入口才用 `block_insert_after --block-id 0` 插入一个普通链接段落，不新增标题。每次 FAQ 写后复查目标标题及入口；不得猜测锚点。

若本次仅要求修改入口或 Skill，不触发群消息重新汇总，不推进水位。其余更新仍遵守增量规则。

### 1. 定位群聊

优先使用用户身份并按名称搜索；先尝试完整名称，未命中时使用“语义地图”等短关键词。不要用 chat-list 代替搜索。

```bash
lark-cli im +chat-search --as user --query "语义地图建图专项测试群" --format json
lark-cli im +chat-search --as user --query "语义地图" --format json
```

记录精确的 `chat_id`（通常为 `oc_...`），确认名称后再继续。

### 2. 读取消息并下载素材

```bash
lark-cli im +chat-messages-list --as user --chat-id <chat_id> \
  --order asc --start "<水位时间减 24 小时>" --page-size 50 --page-all --page-limit 1000 \
  --no-reactions --download-resources --format json
```

保留完整 JSON。将问题与后续答复按时间/线程配对，提取：现象、原因、解决步骤、验证结果、适用版本/限制。默认脱敏内网 IP、账号、token 和机器凭据；只有用户明确要求时才原样呈现。

### 2.1 增量同步与时间水位（每次调用必须遵守）

- 先从目标文档“常见问题”节读取 `增量同步水位：YYYY-MM-DD HH:mm（+08:00）；最后处理消息：om_...`。第一次没有水位时才全量读取。
- 后续以水位前 24 小时作重叠窗口，用 `--start` 拉取，按 `message_id` 去重；处理水位之后的新消息，以及重叠窗口内有修改时间或内容差异证据的已编辑消息。不要仅按 `create_time` 过滤而遗漏旧消息编辑；不重新总结未变化的历史内容。新回复关联旧问题时，按需补读原线程并更新原条目。
- 只处理新消息或内容确实变化的消息；旧问题没有新证据时不要重新生成段落、重复上传截图或重复引用原话。
- 若没有新消息，保持文档不变并报告“已是最新”；不要从头重建或再次追加同一套总结。
- 成功写入后才把水位更新为本次已处理消息中最大的 `create_time` 和对应 `message_id`；更新失败不得推进水位。

### 3. 读取目标 Wiki 的现状

```bash
lark-cli docs +fetch --as user --doc "<document_id>" \
  --scope outline --max-depth 3 --detail with-ids --format json
lark-cli docs +fetch --as user --doc "<wiki_url>" \
  --scope section --start-block-id <常见问题标题block_id> \
  --detail with-ids --doc-format xml --format json
```

找到“常见问题”标题和该节最后一个现有 block。记录读取结果中的 `data.document.document_id`；后续正文读写优先使用这个底层文档 ID，不要把 Wiki 节点管理当成正文写入。不得修改标题、既有列表或既有资源。

先检查该节是否已有本 Skill 生成的摘要/修订版。若存在多个总结，只保留一个名为“语义地图建图问题提取”的完整版本；按 `with-ids` 返回的 block_id 删除旧总结的全部顶层 block 和列表项，保留原始 FAQ 列表与其他章节内容。删除后重新 fetch，再写入或校正唯一版本，避免重复追加。

### 4. 追加图文 FAQ

使用 `docs +update` 的局部 block 指令：同主题更新原有 h3/段落，新主题才在唯一的“语义地图建图问题提取”标题下追加 h3；不要再创建第二个总标题。XML 中本地素材路径以当前 CWD 为基准，使用 `@./...`：

```bash
lark-cli docs +update --as user --doc "<document_id>" \
  --command block_insert_after --block-id <目标主题或该节最后现有block_id> \
  --content '<h3>新的问题主题</h3><p>经原始消息核实的问题与解决办法……</p>'
```

推荐内容结构：

1. 一句话结论/适用范围；
2. 问题现象；
3. 原因；
4. 解决办法（编号步骤）；
5. 验证方式与注意事项；
6. 代表性截图（`<img path="@./lark-im-resources/..." width="..." caption="..."/>`）；
7. 证据来源与整理日期。

用表格或 callout 统一呈现状态；截图只选能解释操作的代表性素材，避免上传重复或含敏感信息的图片。复杂流程可使用 Mermaid 白板，但更新已有白板时必须复用原 token。

## 完整性要求

每次整理必须优先覆盖并单独展开原“常见问题”中的两条：

- “viewer连接不上（开vpn 云枢）”：保留 Catalina/Flow 的原话，明确 Wi‑Fi + VPN（云枢）、health/端口检查和网络故障与服务故障的区分，并插入群内原始入口/连接截图。
- “录制语义建图bag包，机器要移动”：保留 Catalina 关于“机器人在原地没有动”“采集时间太短，走一圈几分钟看看”“bag 包中的数据输入有点问题”的原话，说明建图阶段与定位阶段的区别、建议采集时长/覆盖范围、RGB/Depth 变化检查，并插入群内原始失败截图。

不要只给一句结论；每条问题至少包含现象、原话、原因、编号处理步骤、验证标准、失败时应收集的证据和一张对应原始截图。最终“常见问题”下只保留一套去重后的完整总结。

### 5. 写后验证

```bash
lark-cli docs +fetch --as user --doc "<wiki_url>" \
  --scope section --start-block-id <常见问题标题block_id> \
  --detail with-ids --doc-format xml --format json
```

检查：原有标题和内容仍在；新 FAQ 位于“常见问题”节内；图片可见；没有误改其他章节；更新返回 `result=success` 且无未处理 warnings。

## 权限

| 操作 | 所需权限 |
|---|---|
| 搜索群、读取群消息和素材 | `im:chat:read`、`im:message:readonly`（或等效消息读取权限） |
| 读取/更新 Wiki 正文 | `docx:document:readonly`、`docx:document` |

## 安全约束

- 写入前必须有用户明确意图；用户已明确要求时可直接执行。
- FAQ 正文只在文末“常见问题”节内局部更新；章节外仅维护开头的一条跳转链接。允许删除本 Skill 生成的重复摘要，但不得删除或改写原始 FAQ 列表、其他章节或用户手工内容。合并重复摘要前先保留其中独有的证据、解法和原图，不能直接删掉独有内容。
- 不输出 appSecret、access token、device code 等密钥。
- 遇到权限错误时按 `lark-shared` 处理：user 身份走最小 scope 增量授权，bot 身份引导管理员开通 scope。
