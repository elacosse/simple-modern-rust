# simple-modern-rust

A small Rust command-line application.

```sh
cargo run -- Ada
```

See [installation](installation.md), [development](development.md), [publishing](publishing.md), and [optional agent skills](agent-skills.md). Licensed under the [MIT License](LICENSE).

## Create a project from this template

Create a GitHub repository from this template, clone it, and run `python3 bootstrap.py`. The script prompts for project metadata; run `python3 bootstrap.py --help` for non-interactive options. Review the generated changes and the manual steps it reports. Python 3 and Rust/Cargo are prerequisites for bootstrap; Python is otherwise needed only for the template's own tests.

Template maintainers: after intentionally modifying files checked by bootstrap, run `python3 scripts/refresh_bootstrap_hashes.py` and `make template-test`.
