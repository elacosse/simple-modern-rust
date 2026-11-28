---
name: multi-model-review
description: Run Claude, Gemini, and Codex in parallel via devtools/review.sh for a two-axis (Standards + Spec) review, verify unique catches and disagreements against the codebase, and write a structured synthesis (archived automatically when tied to an OpenSpec change).
---

Run a multi-model, two-axis (**Standards** + **Spec**) read-only review using `devtools/review.sh` (configured by `devtools/review.toml`) and synthesize the three independent reports without merging or reranking across axes.

The runner disables CLI sandboxes and approval prompts. The prompt requests a read-only review but cannot enforce it. Outer environment restrictions still apply.

## Steps

1. **Determine review scope, per-model overrides, and OpenSpec change context**
   - Resolve the diff scope: if the user supplied a fixed point (`--base <ref>`, e.g., `main`, a commit SHA, tag, or `HEAD~5`), pass `--base <ref>`. If no target flags or paths were supplied, `devtools/review.sh` defaults to current uncommitted changes.
   - Parse any per-model directives from the user's invocation (e.g. lines like `codex - medium - focus on race conditions`, `gemini - high - check OpenSpec alignment`, `claude - low`):
     - If the user named specific models (1, 2, or 3), pass `--models <comma-separated-list>` so only those run.
     - For each model with a specified reasoning effort (`low`, `medium`, `high`), pass `--effort <harness>=<level>`.
     - For each model with a specific instruction, pass `--model-prompt "<harness>=<instruction>"`.
     - If the user specified an explicit model ID (e.g. `gpt-5.4`, `claude-opus-4-6`), pass `--model-id <harness>=<id>`.
     - Any omitted model settings fall back to `devtools/review.toml` defaults (`reasoning_effort = "medium"`).
   - Check whether this review belongs to an active OpenSpec change (explicitly named by the user, or the sole active change under `openspec/changes/` excluding `archive/`). When reviewing an active OpenSpec change, pass `--change <name>` so all review outputs are stored under `openspec/changes/<name>/reviews/<timestamp>/` and archived automatically by `openspec archive`.
   - If the user passed a non-OpenSpec spec path or shared focus instructions, include them via `--prompt "..."` or positional paths.

2. **Invoke the bash runner**
   - Run `./devtools/review.sh` with the resolved flags, for example:
     ```bash
     ./devtools/review.sh --change "<change-name>" --base main \
       --models codex,claude \
       --effort codex=high --effort claude=low \
       --model-prompt "codex=focus on race conditions" \
       --model-prompt "claude=check simplification opportunities"
     ```
     or with all defaults from `devtools/review.toml`:
     ```bash
     ./devtools/review.sh --base main --prompt "Spec path: docs/feature.md"
     ```
   - Capture the printed run directory path (`Review run complete: <run-dir>`).
   - If the runner exits non-zero because all enabled harnesses failed (or `--strict` failed), inspect `<run-dir>/meta.json` and any `*.stderr.log` files and report the exact failure to the user.

3. **Read all run outputs**
   - Read `<run-dir>/meta.json` to see which models succeeded, failed, timed out, were missing, or were skipped.
   - Read every available raw report: `<run-dir>/claude.md`, `<run-dir>/gemini.md`, and `<run-dir>/codex.md`.

4. **Verify unique catches and disagreements against the codebase**
   - Do **not** blindly average or paste the three reviews together, and do **not** merge or rerank findings across the **Standards** and **Spec** axes.
   - Whenever only one model flags an issue, or two models disagree on a finding, open the referenced file(s), line(s), and spec/standards doc directly in the repository to verify whether the finding is real or a false positive.
   - Preserve the Standards distinction: documented repo standard breaches can be `[hard]` violations, while Fowler baseline smells are always `[judgment]` calls and are suppressed if a documented repo standard endorses them. Skip anything automated tooling already enforces.

5. **Write `synthesis.md` into `<run-dir>`**
   - Save the synthesized review to `<run-dir>/synthesis.md` keeping the two axes strictly separate:
     ```markdown
     # Multi-Model Review Synthesis

     ## Run Status
     - **Run directory:** `<run-dir>`
     - **Scope:** <change / base / paths / prompt>
     - **Invocation:** <original user invocation instructions, per-model reasoning efforts, and any shared or per-model custom instructions (or `defaults`)>
     - **Models:** claude (<status>, effort=<level>), gemini (<status>, effort=<level>), codex (<status>, effort=<level>)
     - **Raw reports:** `claude.md`, `gemini.md`, `codex.md`, `meta.json`

     ## Standards
     ### Consensus (2-3 Models)
     - **[hard|judgment]** `path/to/file:line` — **Rule or Smell** *(flagged by: ...)*: Evidence and suggested fix.

     ### Verified Unique Catches (1 Model, Confirmed in Code)
     - **[hard|judgment]** `path/to/file:line` — **Rule or Smell** *(flagged by: ...)*: Verified evidence and suggested fix.

     ### Disagreements & Trade-offs
     - Topic, each model's position, codebase evidence, and human decision needed.

     ## Spec
     *(If no spec exists, write `No spec available.`)*
     ### Consensus (2-3 Models)
     - **[missing|scope-creep|wrong]** `path/to/file:line` — **Spec quote** *(flagged by: ...)*: Explanation and fix.

     ### Verified Unique Catches (1 Model, Confirmed in Code)
     - **[missing|scope-creep|wrong]** `path/to/file:line` — **Spec quote** *(flagged by: ...)*: Verified explanation and fix.

     ### Disagreements & Trade-offs
     - Topic, each model's position, spec/codebase evidence, and human decision needed.

     ## Summary
     One-line summary: total findings per axis and the worst issue *within each axis* (if any). Do NOT pick a single winner across axes.
     ```
   - When `--change <name>` was used, remind the user that all files in `openspec/changes/<name>/reviews/<timestamp>/` (raw reports, `meta.json`, and `synthesis.md`) can be committed and will move into `openspec/changes/archive/` automatically when the change is archived.

6. **Present the synthesis to the user**
   - Present the two-axis synthesis concisely in chat with clickable links to `synthesis.md` and the raw model reports.
