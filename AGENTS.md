# AGENTS.md — Repository Engineering & No-Slop Protocol

## Core Mandate
Optimize for **human comprehension, minimal diffs, and root-cause fixes**—not lines of code generated. Treat human review attention as the scarcest resource.

## Mechanical Guardrails (Mandatory Before Handoff)
Run these commands and resolve all errors before concluding any task:
- **Full Check (Recommended):** `make check` (runs `cargo fmt --check`, `cargo clippy`, `cargo doc`, `typos`, `actionlint`, `yamlfmt`, and `cargo test`)
- **Format & Lint:** `make format` (`cargo fmt --all`) and `cargo clippy --locked --all-targets --all-features -- -D warnings`
- **Typecheck:** `cargo check --locked --all-targets --all-features`
- **Single-File Verification:** `./scripts/verify_file.sh <path>`
- **Targeted Tests:** `cargo test --locked --all-features <test_name>`

## Architectural & Anti-Slop Boundaries
- **Subtraction over addition:** Prefer deleting dead code or simplifying existing modules over adding new abstractions, wrapper types, or helper files.
- **No silent workarounds:** Fix broken upstream logic rather than masking failures with ignored `Result`s, fallback defaults, or lint suppressions (`#[allow(...)]`).
- **Explore before writing:** Read existing module patterns and shared utilities before introducing new ones. Zero speculative features.
- **Dependency freeze:** Never add new crates to `Cargo.toml` without explicit human approval. When approved, update and commit `Cargo.lock`.
- **Two-strike rule:** If a mistake or lint failure occurs twice, propose a concrete rule addition to this file or a deterministic linter/test guardrail.

## Execution & Handoff Protocol
1. **Plan First (Non-Trivial Tasks):** For multi-file or architectural changes, output a 3–5 bullet plan (what changes, what gets deleted, key trade-offs) and wait for approval before writing code.
2. **Handoff Summary (<= 5 Bullets):**
   - **Intent / Root Cause:** What was actually broken or needed.
   - **Changes:** Exact files modified/deleted and why.
   - **Verification:** Commands run and pass status.
   - **Human Review Focus:** Specific high-stakes logic, edge cases, or assumptions requiring human judgment.

## Human Communication (ASD-STE100)
Write all human-facing prose (plans, status updates, handoff summaries, and explanations) in **ASD-STE100 (Simplified Technical English)**:
- **Sentence length:** Keep instructions to <= 20 words and descriptions to <= 25 words. Put one idea in each sentence.
- **Active voice & simple verbs:** Use active voice and simple tenses (imperative for steps; simple present, past, or future for facts). Replace weak verb phrases with direct verbs (`check`, not `perform a check`).
- **Noun clusters:** Limit noun clusters to <= 3 words.
- **Consistent, plain words:** Use one word for one meaning. Avoid idioms, filler, and vague pronouns (`this`, `it`). Use plain terms (`use`, `start`, `stop`, `before`, `if`).
- **Lists:** Use a vertical list for 3 or more items.
- **Technical exemptions:** Code identifiers, file paths, CLI commands, and verbatim error/spec quotes are Technical Names and do not change.

## Project Layout & Template Notes
- Read `README.md` and `development.md` before making changes. Keep the CLI small and test observable behavior.
- See `agent-skills.md` for optional OpenSpec and agent skills; do not make Rust builds depend on them.
- See `publishing.md` before creating a release.
