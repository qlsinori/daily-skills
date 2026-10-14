---
name: report
description: Summarize work completed during a recent date range by reading matching local Codex and Cursor transcripts plus semantic-map work evidence on configured SSH servers, not only the current conversation. Use when the user invokes /report or $report, asks for a daily, multi-day, weekly, monthly, or custom-range work report, or wants recent Codex/Cursor-assisted work consolidated with duplicate sessions removed and organized by importance, difficulty, actions, and outcomes.
---

# Work Report

Build an evidence-based work report from the user's local Codex session history. Keep all discovery read-only.

## Resolve the reporting period

- Use explicit start and end dates when provided.
- Interpret “本周” as Monday through today in the user's local timezone.
- Interpret “最近 N 天” as N calendar dates including today.
- Default to the latest 7 calendar dates when no period is provided, and state that assumption.
- Use the timezone from the environment context. Fall back to the system timezone.

## Collect the complete history

Run `scripts/collect_work_history.py` from this skill directory with the resolved dates and timezone. Start with the digest Markdown format. The default report invocation also enables the Cursor collector:

```bash
python3 <skill-directory>/scripts/collect_work_history.py \
  --start YYYY-MM-DD \
  --end YYYY-MM-DD \
  --timezone Area/City \
  --include-cursor \
  --cursor-root ~/.cursor/projects \
  --all-ssh-hosts \
  --ssh-config ~/.ssh/config \
  --format markdown \
  --output <temporary-directory>/work-history.md
```

The script reads the local Codex index and sessions, local Cursor agent transcripts under `~/.cursor/projects/**/agent-transcripts/`, and matching remote Cursor agent transcripts from every concrete `Host` in the configured SSH file. Remote roots default to `~/.cursor/projects` and `~/.codex/sessions`; pass `--remote-cursor-root` to add a known server-side transcript root. Cursor collection is restricted to `.jsonl`, `.md`, and `.txt` files under `agent-transcripts` whose content matches semantic-map keywords and whose file timestamp or embedded date falls in the report range. It does not read Cursor caches, terminal dumps, agent-tool logs, databases, `auth.json`, configuration secrets, shell history, unrelated documents, email, calendar, or chat applications unless the user explicitly adds them.

The remote scan is read-only and uses non-interactive SSH with a short connection timeout. Every inaccessible host is listed as an access limitation rather than treated as evidence. SSH aliases pointing to the same server may produce mirrored records; merge those records with the normal duplicate-session pass. “All servers” means all concrete hosts visible in the selected SSH config, not arbitrary network discovery.

## Default data-source profile

For this user, the following sources are part of the default report scope and do not need to be restated for every report request:

- **Local Codex history:** all matching local Codex sessions in the requested date range, including sessions routed through CC-Switch providers such as DeepSeek or Kimi. These are normally stored in the same `~/.codex/sessions/**/*.jsonl` tree; identify the provider from session turn metadata rather than assuming a separate transcript directory.
- **Local Cursor history:** matching Cursor agent transcripts under `~/.cursor/projects/**/agent-transcripts/`, including the semantic-map service work performed from memory-module worktrees. Read user requests and outcome-bearing assistant text; ignore terminal/tool chatter unless it is the only evidence of a material result.
- **CC-Switch metadata:** inspect `~/.cc-switch/logs/` read-only only to confirm provider routing and time coverage. Treat these logs as routing metadata, not as independent work evidence; do not expose keys, request payloads, or credentials.
- **Remote SSH work context:** the SSH-accessible project directories, logs, commits, task notes, and Codex/session records related to the user's ongoing work. Inspect read-only and select only material relevant to the report period and project themes.
- **Remote Cursor history:** on every concrete SSH host from the selected config, inspect the server-side Cursor agent-transcript roots for semantic-map service work. Search terms include `语义地图`, `语义建图`, `semantic map`, `semantic_mapping`, `memory_module`, `hydra_custom`, `mapdb`, and `建图服务`; add project-specific terms with `--semantic-keyword` when needed.
- **Feishu semantic-map and annotation context:** the user's relevant Feishu group conversations, documents, Wiki pages, and linked project materials concerning semantic mapping, annotation, dataset quality, and related delivery work. The standing context includes `语义地图建图专项测试`, `语义建图小组`, `语义地图-目标检测-图片标注任务`, the daily-report Wiki, and the semantic-map operating guide; follow related links and conversation history when accessible.

Use this default source profile automatically. Do not ask the user to repeat these sources. The user can narrow or override it with instructions such as “只看本地会话” or “不读取飞书”。 If a default source is unavailable, partially accessible, or contains only requests without completion evidence, state that limitation and do not fill the gap by inference. Merge duplicate reports or mirrored session tails across local Cursor, remote Cursor, Codex, and Feishu sources while retaining unique implementation evidence.

Do not search unrelated chats, other people's private conversations, or unrelated server directories. Other linked sources are included only when the user names them or provides a link and the available connector/authentication can access them.

Inspect every included session. Use `--session-id <id>` to produce a focused extract when a session is too large or an outcome needs closer inspection. Use `--detail full` only when the digest omitted necessary evidence.

When the user mentions DeepSeek, Kimi, CC-Switch, or another alternate model, search both Codex session metadata and the local CC-Switch logs. Merge alternate-model transcripts with their Codex session by session ID and timestamp; never count a CC-Switch request log as a separate session or as completion evidence.

Treat the current conversation as one of the sessions, not as the sole source. Report the number of source sessions and exact date range. Merge duplicated transcript history from resumed or forked conversations while preserving each branch's unique tail. Retain separate sessions that merely cover the same project.

When a report includes Cursor records, identify the source (`Cursor local` or the SSH host), the transcript path, and the project/worktree when available. Treat Cursor compaction summaries as historical evidence from the same root task, merge them with the root transcript when their copied prefix matches, and do not count a compaction segment as an independent work item.

## Split work at the task level

A session is an evidence container, not a report item. Split one session into separate tasks whenever the user changes the work object, repository/module, target service or server, acceptance criterion, or requested outcome. A single Cursor session may therefore produce several report items. For example, a session containing “语义地图适配 ex002”“Benchmark 场景可视化”“评测结果分析” and “地图编辑多源版本可视化” must produce four task entries, with their own actions, evidence, status, and source label.

Build the task ledger before drafting. Each row records the task title, source label, session ID, transcript path, project/worktree, target host or service, user request, completion evidence, status, and report disposition. Keep copied prefixes together but preserve distinct tails when a resumed or forked session contains separate tasks. A task that has only a request remains “请求中” or “进行中”; do not let a completed neighboring task make it look completed.

Read every in-range turn, not just the last requests or final replies. Digest shortening affects individual message length only; use full text to resolve omissions. For long Cursor sessions, inspect the dated user turn and its subsequent assistant outcomes together. File modification time and compaction creation time do not prove that every historical task happened in this period; label undated summaries as historical context and verify outcomes in original turns. Preserve ongoing follow-up separately from work completed before the period.

Every task entry must show its source explicitly in the title or first sentence using one of these labels:

- `Codex·本地` for a local Codex transcript.
- `Codex·<IP 或主机>` for Codex/session or project evidence read through a remote host.
- `Cursor·本地` for local Cursor agent transcripts.
- `Cursor·<IP 或主机>` for Cursor transcripts read on a remote server.
- `飞书·<群聊或文档>` for a Feishu conversation or document.

If duplicate copies from multiple sources describe the same task, retain all confirmed source labels, for example `来源：Cursor·本地；Cursor·10.136.27.172`, and merge the evidence once. Do not write only “来源：Cursor” or “来源：远程”，because that hides whether the work came from the local machine or a specific server. The generated digest includes source labels at the session level; the final report must carry them down to each split task.

Source means where the evidence was read, while target means where the work ran or was deployed. A local Cursor session deploying to 10.136.29.157 is `来源：Cursor·本地；目标：10.136.29.157`, not `Cursor·10.136.29.157`. Include the source on every independent numbered item and every workload-bearing subitem; a parent theme's source does not cover children from other tools. Keep a short session ID or evidence link beside each task when needed for traceability. A task may have several sources; do not infer remote provenance merely from an IP mentioned in local text.

## Build a session coverage ledger

Before drafting, build a private coverage ledger with one row per unique session or resumed/forked root thread in scope. Record the source, session ID, date range, title, user requests, work object, completion evidence, status, and report disposition.

- Inspect all user messages and all assistant final answers. Also inspect commentary or progress messages containing completed actions, fixes, deployment results, test results, or changed decisions; final outcomes alone are not sufficient.
- Inspect each large session in date order and extract its per-turn outcomes before clustering themes.
- Inspect remote SSH sessions and mirrored/forked transcripts as separate evidence sources, then merge copied prefixes while preserving unique tails.
- Treat analyses, diagnoses, scripts, documentation updates, deployments, and operational fixes as work items when they produced a decision, unblocked delivery, or changed the verified state.
- Include small completed items under the relevant parent theme with `已修复：`, `已处理：`, or `已补齐：` lists. Do not let thematic compression hide distinct completed problems.
- Record a specific exclusion reason for every non-trivial session that does not produce a report item, such as greeting only, request without evidence, duplicate transcript, unrelated personal support, or inaccessible source.
- Do not finalize the report while any non-trivial session has no disposition. Reconcile the ledger against the report and source note before drafting.

The coverage ledger is an internal audit artifact; do not paste it into the report unless the user asks for it.

## Establish evidence and status

Classify each item before writing:

- **Completed:** the user explicitly described it as completed, or a later final outcome records implementation and verification.
- **In progress:** the history shows work started but no completion evidence.
- **Requested only:** the user asked for it, but no later outcome confirms completion. Do not present it as an achievement.
- **Supporting work:** deployment, networking, containers, SSH, remote desktop, or tooling. Include it only when it materially enabled project delivery; otherwise omit it or place it in a short supporting-work item.

Include concise coordination work when Feishu or project records show that the user clarified requirements, aligned UI/process definitions, collected field feedback, coordinated issue ownership, or confirmed acceptance criteria. Treat this as a supporting-work item unless there is evidence of a separate delivered result. Do not omit it merely because it has no commit or test count. Keep it brief and distinguish alignment from implementation.

For Feishu chat attribution, count work toward the user only when the records identify the user as the speaker, initiator, assignee, or explicit follow-up owner. Do not count messages written by other participants merely because they concern the user's project, and do not infer ownership from group membership, being mentioned, or being present in a meeting. If ownership is unclear, list it as team context or exclude it from the user's work summary.

For this account, verify the Feishu user identity before attributing chat work; the current identity is `Flow`. Do not attribute messages from `Catalina` or other participants to Flow. When summarizing a Feishu daily-report document, treat it as a mixed project log unless each item can be matched to Flow's own messages or explicit follow-up. In the final report, put a standalone bold `飞书工作总结` paragraph before the per-chat detail.

Write the report in an impersonal, action-first project voice. Do not use any first-person pronoun. Start with the work object or an action verb, for example “完成……”“修复……”“验证……”“推进……”. Do not refer to the user as “Flow” in the main report. Keep third-person attribution only in the source note or when distinguishing another participant's work.

Prioritize plain-language readability over internal shorthand. Convert abstract management or engineering labels into the concrete symptom, affected workflow or user, action, and result. Do not use an abstract label as a substitute for explaining what happened. For example, write “标注审计查询变慢，原因是缺少索引，每张图都会触发全表扫描” instead of leaving it as a performance label; write “已提交但未质检的标注框没有计入工作量，现已纳入统计并上线” instead of a statistics-method label. Explain unavoidable technical terms once in the same sentence.

Prefer the latest confirmed state when the same feature was revised repeatedly, but do not drop independent fixes merely because they belong to the same theme. Consolidate the narrative and preserve distinct completed problems in labeled sublists. Preserve meaningful numerical evidence such as dataset counts, test results, version identifiers, and deployment ports only when present in the history.

Do not use an earlier generated work report as independent completion evidence. Trace its claims back to the original user-reported work or implementation outcome in the source sessions.

Do not expose credentials, tokens, cookies, private keys, or irrelevant personal information. Do not perform writes to project repositories, services, or business data while producing a report.

## Write the report

Read [references/report-style.md](references/report-style.md) before drafting. Unless the user requests another format, produce Chinese copy that is ready to paste into a status report. Optimize first for complete coverage, then for readability; do not apply a low item cap when many independent fixes were completed.

For every main item, cover these four points in cohesive prose:

1. What was done.
2. Why it matters.
3. What made it difficult.
4. How it was handled and what result was verified.

Add the task source and status to the same paragraph, for example: “来源：`Cursor·本地`；状态：已完成。” For a task backed by more than one transcript, list the concrete local/remote labels and keep the session IDs in the source note.

Use this fixed reasoning order when drafting each item: **why the work was needed → why it mattered → why it took time or was difficult → how it was handled → what changed after the work**. Lead with the project value and the verified result; do not lead with a release number, commit hash, raw test count, or a string of implementation telemetry. Keep those details only when they are needed to support the result.

When the history contains several independent fixes or improvements under one feature, add a list after the main paragraph instead of packing them into a semicolon-separated sentence. Use `已完成：` for important workload-bearing outcomes and `已修复：` or `已补齐：` for secondary follow-up items.

Every list item must be one complete sentence, not a noun phrase or terse label. State the action, the object or problem, and the result or verification. The `已完成：` list is curated rather than exhaustive: keep the important workload-bearing items, typically 3–7 per theme, and move secondary fixes, UI polish, small status corrections, and routine follow-ups into the preceding paragraph. Bold the main technical object or verified outcome inside each `已完成` item.

```markdown
已完成：

- 完成 **2D 建图一键联合流程重构**，将连接、启动、停止保存和上传合并为并发流程，减少现场重复操作。
- 完成 **服务器定位建图从容器接口确认到真机出图的完整验证**，3D 和 2D 作业均产出可固化地图包。
- 完成 **标注工作量漏算修复**，将未质检但已提交的标注框计入工作量并部署到生产环境。

已修复：

- 修复 SSH 输出撑宽页面的问题，通过限制网格和子元素最小宽度避免移动端横向溢出。
- 修复压缩 MCAP 魔数常量错误，避免有效压缩包被误判为无效文件。
```

Only list work supported by the source sessions. Combine closely related fixes on one sentence when that improves readability, and do not turn every command, test case, or intermediate attempt into a separate item. Avoid generic agent narration such as “完成了相关工作”“进行了全面排查” unless the sentence states the concrete problem, action, and result.

Use restrained inline bold emphasis inside the main prose to surface the key problem, the key action, and the verified result, for example: **数采预检早于定位启动** and **数采文件和地图包下载接口均验证成功**. Do not bold the whole paragraph, every technical term, or every sentence. Main work-theme names may be bold when useful. The labels `已完成：`, `已修复：`, and `已补齐：` and the text that follows them must remain plain text. When several independent technical problems are mentioned, do not leave them in a dense sentence; move them into an evidence-backed plain-text list under one of those labels.

Keep distinct technical themes separate, but combine small follow-up fixes under their parent feature. Distinguish facts extracted from history from reasonable plans or recommendations. Never invent test findings, failure modes, metrics, or business impact.

For Feishu and other collaboration records, summarize the communication outcome in one or two sentences: what was aligned, which project decision or follow-up it enabled, and whether it remains open. Do not list routine chat messages individually.

End with a short next-step section only when requested or when the reference style clearly calls for it. After the main report, add a separate Feishu section in this fixed order: first write one detailed cohesive paragraph beginning with bold `飞书工作总结：`, suitable for pasting directly into a status report; then expand the evidence in detail. Each detailed entry must lead with a work-theme title and identify the exact source chat or document in parentheses, for example `**目标检测模型误识别分析与测试（来源：《yoloworld标注训练》）**`; do not use the raw chat name as the title by itself. The summary paragraph must state the work objects, the user's coordination actions, the decisions or rules aligned, the field or testing feedback collected, and the delivery impact or remaining follow-up. It should stand alone rather than merely naming the chats. Use a few inline bold phrases for the main coordination outcomes, without bolding the whole paragraph. The detailed entries should state what each source summarized—requirement alignment, field feedback, bug triage, labeling rules, release/deployment notification, or acceptance decision—and distinguish confirmed decisions from open follow-ups. Then add a compact source note stating the date range, source types actually read, session/conversation counts where available, duplicate count, access limitations, and deliberately excluded support-only topics.

## Invocation examples

- `$report 本周`
- `$report 最近三天，按照为什么重要、难点、怎么做来写`
- `$report 2026-08-01 到 2026-08-15，精简版`
- `$report 汇总最近一个月的工作，并区分已完成和进行中`

Prefer `$report` for guaranteed explicit skill selection in Codex. Treat a plain user message such as `/report 本周` as an implicit trigger when it reaches the agent.
