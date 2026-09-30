---
name: assist-code-reading
description: Create Chinese code-reading helper documents by tracing repository entry points into explainable training and inference call chains.
metadata:
  short-description: Build repository code-reading guides
---

# 辅助代码阅读

Use this skill when the user wants a repository explained through a readable Markdown guide, especially when an existing training/inference document should be rewritten for another codebase.

## Outcome

Produce a Markdown document that lets a reader follow the real code from an entry point to model/environment outputs. The document should teach the codebase, not merely summarize its README. Keep claims tied to files, symbols, shapes, commands, or observed results.

## Workflow

1. **Identify the artifact and audience.** Find the requested output Markdown file and inspect its existing style. Preserve useful conventions such as Chinese terminology, local links, diagrams, and the rule that code and explanation appear together. If the user names a prior document as the pattern, treat that document as the format reference.
2. **Discover entry points.** Use `rg --files`, `rg` for `train`, `infer`, `eval`, `server`, `predict`, `step`, and read the smallest set of source files that covers the path. Start at CLI/server/evaluation entry points, then follow direct imports and calls.
3. **Build a call-chain map before writing.** Record for each stage: file and symbol, input shape/units, transformation, output shape/units, and the next caller. Separate environment preprocessing, model encoding, diffusion/optimization, action selection, and postprocessing.
4. **Write the guide around the call chain.** Explain each important stage with a short code excerpt or a precise local file link followed immediately by a plain-language explanation. Do not put a long detached code dump before its explanation.
5. **Translate vocabulary.** Add a compact table mapping repository terms to the concrete object or tensor they represent. Explain confusing names such as `agent`, `goal`, `memory`, `trajectory`, `critic`, `checkpoint`, and `rollout` in the project's own context.
6. **Separate training from inference.** Describe the actual training entry point and the actual inference entry point independently. If a repository has only inference code, say so. If a smoke test or synthetic training helper is added, label it as a smoke test and never present it as a paper-quality result.
7. **Document evidence and limits.** Include commands that were actually run and their observable results when validation was performed. Distinguish repository facts, local modifications, and assumptions. Call out external assets, licenses, model checkpoints, simulators, or unavailable data that prevent a full run.
8. **Add a compact visual when it reduces cognitive load.** Prefer a small ASCII or Mermaid flow for the end-to-end path, and tables for shapes/term mappings. Skip visuals that do not clarify a relationship.
9. **Validate the artifact.** Check every local link target, run Markdown/text sanity checks, and run a minimal import or smoke command when the repository permits it. Do not claim success without command output or another concrete observation.

## Writing constraints

- Write in clear Chinese unless the user requests another language; keep source names, symbols, and command flags unchanged.
- Use local Markdown links with absolute paths when the renderer needs clickable files; include a line number for an important symbol when practical.
- Keep one main idea per paragraph. Explain tensor dimensions and units at the point where they first matter.
- Prefer concrete relationships: “`predict_action()` reads `obs` and returns `action`.” Avoid generic machine-learning descriptions that are not tied to this repository.
- Do not invent missing training data, checkpoints, robot hardware, simulator assets, or performance numbers.
- Keep the reusable guide independent of a particular repository. Put repository-specific facts only in the generated document or a task-specific reference, not in this skill.

## Suggested structure

Read [references/document-template.md](references/document-template.md) when creating a substantial guide. Adapt the headings to the repository; do not force sections that do not apply.

## Completion checklist

Before finishing, confirm:

- The document names the main train/infer entry points and follows their real call chain.
- Important symbols have file links and their input/output meaning is explained.
- The terminology table matches this repository rather than a generic framework.
- Full training, smoke training, pretrained inference, and evaluation are clearly distinguished.
- Commands and results are reproducible from the stated working directory.
- External prerequisites and unresolved limitations are explicit.
