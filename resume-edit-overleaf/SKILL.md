---
name: resume-edit-overleaf
description: Edit a LaTeX resume in the user's project, preserve its existing formatting, compile and visually check the one-page PDF, then commit and push the requested resume changes to Overleaf. Use for explicit resume edits or Overleaf publishing requests.
---

# Resume edit and Overleaf publish

负责把已确定的简历内容落到 LaTeX 源文件，并在用户明确要求提交/推送时发布到 Overleaf。默认项目结构是根目录 `resume-zh_CN.tex`、正文 `texs/sections.tex`，但先检查实际路径。

## 修改原则

- 先读取目标段落和相关模板；只改用户要求的内容，保持其他文章、作者、日期、标题、间距和格式不变。
- 论文作者加粗时只加粗用户本人姓名，不要误加粗其他作者；Under Review 等状态放在用户指定的括号内。
- 用户要求“一页”时，优先压缩文字和项目描述，避免先全局改字体；必要时再做最小的垂直间距调整。
- 项目经历每条都要形成“负责对象 → 采用方法 → 训练/数据处理 → 评测或部署结果”的完整因果链，避免把模型名、接口名和训练方法并列堆成术语清单。
- 简历面向外部读者时，把团队内部平台名和代号改成可理解的能力描述；只有对岗位有明确价值的公开技术名才保留。提交前检查是否残留 `asaa2`、占位符或孤立乱码。
- 替换项目中的模型名时，先回查团队原始记录确认其实际接入、训练或评测范围；若保留公开模型名，还要以该模型的官方论文、项目页或官方代码库核对其技术定位，避免把底座、内部实现或调研对象误写成项目主体。
- 用户指定历史简历版本作为参考时，先读取对应段落；仅继承其中可核对的模型、训练流程、基准任务或指标，并据此改写为当前简历的风格。
- 用户只要求改简历时，不把分析 Markdown、临时 PDF、日志或图片上传到 Overleaf。

## 编译与视觉检查

1. 在编辑前检查 Git 状态和 Overleaf remote；若工作树干净，先 `git pull --rebase origin main`。
2. 用 XeLaTeX 编译：

   ```powershell
   xelatex -interaction=nonstopmode -halt-on-error resume-zh_CN.tex
   ```

   若出现 `spawn xelatex ENOENT`，先用 `Get-Command xelatex` 查找 MiKTeX/TeX Live 的绝对路径，使用该路径编译或临时加入当前进程的 PATH；不要把错误当成源文件语法错误。

3. 检查编译退出码、`resume-zh_CN.pdf` 是否生成、`pdfinfo` 是否为 1 页，以及日志中的 `Overfull`。涉及排版的修改必须用 `pdftoppm` 渲染第一页并查看图片，检查底部是否被裁切、标题是否换行异常、日期是否错位。
4. 若一页溢出，先缩短新增文字或减少新增项目间距；修复后重新编译和查看，不要用 `-draft` 或忽略错误掩盖问题。

## 提交到 Overleaf

只有在用户明确说“推送/提交到 Overleaf”或等价表达时执行发布：

```powershell
git add -- resume-zh_CN.tex texs/sections.tex
git commit -m "Describe the resume change"
git pull --rebase origin main
git push origin main
```

- 推送前确认 diff 只包含预期简历源文件；禁止 force push。
- 若 rebase 有冲突，停止并检查冲突内容，不要自动覆盖远端修改。
- 推送后报告编译结果、页数、提交号和实际改动文件；若用户未要求推送，只保留本地修改并说明状态。
