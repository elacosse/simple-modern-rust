# Optional agent skills

[OpenSpec](https://openspec.dev/) can help plan and track changes. Install its CLI only if you want to use it, then run `openspec init --tools codex,claude --profile core` to set up integrations for your assistants. See the [OpenSpec quickstart](https://openspec.dev/docs/quickstart). Review and commit the generated project configuration and agent files. OpenSpec and agent skills are not required to build or test the Rust project.

## Multi-model review

The `multi-model-review` skill uses Python 3.11 or later and the local Claude,
Antigravity, and Codex CLIs. It does not require Python for Rust builds.
The runner disables CLI sandboxes and approval prompts. The prompt requests a
read-only review, but cannot enforce it. Host restrictions still apply.
