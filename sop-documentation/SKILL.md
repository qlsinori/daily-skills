---
name: sop-documentation
description: Create concise, executable, image-grounded SOPs from screenshots, UI workflows, or operational notes, with sequential captions and Feishu-ready Markdown or Word output.
metadata:
  short-description: Create image-grounded operational SOPs
---

# 图文 SOP 编写

把用户提供的截图、界面操作和零散说明整理成测试人员可以照着执行的 SOP。适用于机器人建图、语义地图、工位编辑等需要“步骤与图片一一对应”的流程。

## 工作方式

1. 先确认目标读者、起止范围、实际入口和交付格式。将未完成或用户明确暂不展开的章节保留为占位，不擅自补流程。
2. 以真实页面为依据写按钮和菜单名称。若截图来自错误页面，停止复用并重新确认正确入口；不要用示意图冒充实际界面。
3. 把长句拆成一个动作一个编号步骤。每一步说明入口、操作、结果或检查点；只写操作员需要知道的内容。
4. 图片紧跟对应步骤，图注使用连续的“图 1、图 2……”编号。删除一张图或图注后，重新顺延全部后续编号，并检查图片与图注数量一致。
5. 对有风险的动作（删除、合并、覆盖文件、导出）写出确认点和回退方式。涉及地图文件时先备份旧文件，再用用户指定的原文件名替换，避免要求操作员理解内部切换机制。
6. 在文末提供完成标准或交付检查清单，确保操作者能判断流程是否完成。

## 输出

- 默认先生成可直接粘贴到飞书的 Markdown；保留真实链接、代码格式、图片引用和清晰的标题层级。
- 用户要求 Word 时，再将同一份 Markdown 转为 `.docx`，保留图片、图注、标题、编号和链接，并做渲染检查。
- 图片来源、页面入口或数据格式不确定时，明确标记待确认项，不编造控件、目录或截图。
- 语义地图类流程的具体步骤见 [references/semantic-map-sop.md](references/semantic-map-sop.md)。
- 根据多张界面截图编写工位编辑等 SOP 时，先按图片实际顺序建立操作链，再按用户指定的倒序或图注要求排版；参考 [references/image-to-sop.md](references/image-to-sop.md)。

## 质量检查

- 所有入口、按钮、文件名和目录与来源一致。
- 每个关键操作都有对应图片或明确说明为何没有图片。
- 图注连续、没有跳号、重复或与图片错配。
- 源 Markdown、Word 和压缩包（如有）内容一致。
- 不把服务端密钥、密码或内部凭据写入 SOP；只引用获取凭据的正规位置。
