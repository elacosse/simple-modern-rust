# Proposal: simple-modern-rust

## Goal and scope

Build a sibling of simple-modern-uv for small Rust command-line applications. Preserve its approachable setup, common make commands, documentation, and agent guidance while following Cargo conventions. Start with a single CLI package; libraries, services, embedded projects, and multi-crate workspaces are outside the initial scope.

## Project creation

Use a GitHub template repository and a one-time Python standard-library bootstrap script. Python is a bootstrap prerequisite, not a dependency of the generated Rust project. This keeps the template itself buildable and preserves the existing create-repository, clone, configure workflow. The cost is maintaining the configurator; cargo-generate is a viable alternative if this proves too expensive.

Accept project name, GitHub owner, author name and email, and description. Validate inputs and all expected markers before editing. Update metadata, documentation, license, CLI references, and the lockfile; remove template-only setup files; and report remaining manual steps. Fail safely on unexpected template state. A disposable-project test must exercise a hyphenated name and Cargo's underscore-normalized library identifier.

## Generated project

```text
Cargo.toml
Cargo.lock
rust-toolchain.toml
.cargo/config.toml
src/
  main.rs
  lib.rs
tests/
.github/
  ci.yml
  workflows/               # Publishing supplied but disabled until enabled
Makefile
README.md
development.md
installation.md
publishing.md
AGENTS.md
CHANGELOG.md
LICENSE
openspec/
```

The example CLI uses clap and calls a small greet function in lib.rs, demonstrating separately testable logic and argument handling. Explain that publishing the package also exposes its library target, which can create compatibility obligations. Retain MIT licensing, optional agent skills guidance, and OpenSpec integration; Rust builds must not depend on agent tooling. Do not add dotenv loading, async runtimes, logging frameworks, or a workspace by default.

## Toolchain and development

Pin a concrete stable Rust toolchain, including rustfmt and Clippy. Initially set Cargo's rust-version to that same version; a lower minimum becomes a support promise and must be tested separately. Commit Cargo.lock and use --locked for checks and builds where supported.

| Command | Behavior |
| --- | --- |
| `make setup` | Check prerequisites and install optional Git hooks. |
| `make check` | Read-only formatting, Clippy, documentation, spelling, YAML, and test checks. |
| `make format` | Apply Rust formatting and documented safe fixes. |
| `make test` | Run unit, integration, and documentation tests. |
| `make build` | Build a release binary and verify the source package. |
| `make upgrade` | Update the lockfile for review. |
| `make template-test` | Configure and verify a disposable generated project. |

Select and pin concrete spelling and YAML tools, document how to install them, and ensure setup provides or clearly verifies them. Test their availability before making them mandatory. Do not require Python after bootstrap solely to run the Rust project. Checks must not require Git hooks.

Support the make workflow on macOS and Linux. Document equivalent Cargo commands for Windows and test Cargo builds and tests there. Do not claim full Windows make support without testing its prerequisites.

## Dependency and security policy

Enable a 14-day dependency cooling-off period only if the selected stable Cargo version supports it and an integration check verifies both the policy and an emergency override. Otherwise document the gap; do not require nightly or claim unenforced parity. Lockfile updates are deliberate and reviewed.

Provide an optional RustSec audit command or scheduled workflow, separate from the default local check because advisory data changes and requires network access. Document optional coverage without imposing a universal threshold.

## CI and publishing

The template repository has active CI that runs its checks and exercises generation. Generated projects receive a disabled, manually triggered CI workflow, with documentation recommending push and pull-request triggers once the project is ready.

Publishing is explicitly opt-in: provide a disabled workflow and instructions to enable it. Cargo.toml is the version source of truth; verify that the release tag matches it before publication. Document the initial manual crates.io publication, subsequent trusted-publisher setup, and automated later releases. Distinguish source installation via Cargo from downloadable prebuilt binaries. Cross-platform binary releases are deferred.

## Acceptance criteria

1. A fresh template-derived repository bootstraps with realistic metadata and a hyphenated name, without leftover project placeholders.
2. The generated project passes make check, make build, and its CLI integration test on supported Unix environments.
3. Windows CI verifies the documented Cargo build and test commands.
4. The smoke test verifies packaged crate contents and runs the generated CLI.
5. Template CI exercises the full generation path, invalid input, and failure-safe marker checks.
6. Publishing instructions cover the first manual release and later trusted releases; no publishing workflow runs until the owner enables it.
7. The selected toolchain's cooling-off support is tested and accurately documented.

## Background and references

- [Original Python template](https://github.com/jlevy/simple-modern-uv)
- [Fission Rust template](https://github.com/fission-codes/rust-template)
- [Crate Expectations](https://github.com/qkniep/crate-expectations)
- [Rust GitHub Template](https://rust-github.github.io/)
- [Cargo dependency resolution](https://doc.rust-lang.org/cargo/reference/resolver.html)
- [Cargo minimum publish age](https://doc.rust-lang.org/cargo/reference/unstable.html#min-publish-age)
- [crates.io trusted publishing announcement](https://blog.rust-lang.org/2025/07/11/crates-io-development-update-2025-07/)
