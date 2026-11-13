# simple-modern-rust

A small Rust command-line application.

The example CLI uses [clap](https://crates.io/crates/clap) to parse arguments and calls a separately testable greeting function. Run it from a checkout with:

```sh
cargo run -- Ada
cargo run -- --help
```

For setup, checks, and release instructions, see [installation](installation.md), [development](development.md), and [publishing](publishing.md). [Agent skills and OpenSpec](agent-skills.md) are optional. The project is licensed under the [MIT License](LICENSE).

## Create a project from this template

**simple-modern-rust** is a GitHub repository template for small Rust command-line applications. It is a Cargo-native sibling of [simple-modern-uv](https://github.com/jlevy/simple-modern-uv): it provides a working starting project, common development commands, documentation, and optional agent guidance so you can start building a CLI without assembling the same infrastructure each time.

The template is a single Cargo package with a binary and a small library. The library makes application logic easy to test independently of argument parsing; if you publish the package, its public library API is also published. The generated project includes a pinned stable Rust toolchain with rustfmt and Clippy, a committed lockfile, unit and CLI integration tests, documentation tests, and a Makefile. It intentionally does not add an async runtime, logging framework, dotenv loader, or multi-crate workspace.

### Get started

1. Create a repository from this GitHub template and clone it.
2. Install [Rust and Cargo with rustup](https://rustup.rs/) and have Python 3 available for the one-time setup. From the new repository, run:

   ```sh
   python3 bootstrap.py
   ```

   The script prompts for a project name, GitHub owner, author name and email, and description. For automation, use the corresponding flags shown by `python3 bootstrap.py --help`.
3. Review the generated files and the manual steps reported by the script. The configurator updates project metadata and CLI references, checks that the template is in its expected state, and removes its own setup files. Check crate-name availability separately if you intend to publish.
4. Follow [development.md](development.md) to install the check tools and run `make check`. Replace the example greeting and tests with your application.

Python is required for bootstrap and template-maintainer tests; generated Rust projects do not depend on it. The Makefile workflow is supported on macOS and Linux. The development guide also lists equivalent Cargo commands for Windows.

### What is included

- `make check` runs formatting, Clippy, documentation, spelling, YAML, workflow, and test checks; `make format`, `make test`, `make build`, and `make upgrade` cover common development tasks.
- Generated projects include a manually triggered CI workflow with Unix checks and Windows Cargo builds and tests. Add push and pull-request triggers when the project is ready.
- Publishing to crates.io is opt-in. An example workflow is kept outside the active workflows directory until you configure it; the publishing guide covers the first manual release and later trusted publishing. Prebuilt binary releases are not included.
- OpenSpec and agent guidance are available but are not required for Rust builds. The default project stays focused on a small CLI.

Template maintainers: after intentionally modifying files checked by bootstrap, run `python3 scripts/refresh_bootstrap_hashes.py` and `make template-test` to verify a disposable generated project.
