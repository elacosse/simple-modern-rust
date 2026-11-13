# Proposal: simple-modern-rust

## Goal and scope

Build a sibling of simple-modern-uv for small Rust command-line applications. Preserve its approachable setup, common make commands, documentation, and agent guidance while following Cargo conventions. Start with a single CLI package; libraries, services, embedded projects, and multi-crate workspaces are outside the initial scope.

## Project creation

Use a GitHub template repository and a one-time Python standard-library bootstrap script. Python is a bootstrap prerequisite, not a dependency of the generated Rust project. This keeps the template itself buildable and preserves the existing create-repository, clone, configure workflow. The cost is maintaining the configurator; cargo-generate is a viable alternative if this proves too expensive.

Accept project name, GitHub owner, author name and email, and description. Validate inputs and all expected markers before editing. Restrict names to a documented subset accepted by Cargo and crates.io, reject reserved identifiers and path separators, and check crate-name availability as a separate manual step (availability can change). Escape user values for their destination formats rather than performing unrestricted replacement. Update metadata, documentation, license, CLI references, and the lockfile; remove template-only setup files; and report remaining manual steps.

Stage and validate all changes before applying them, preserve existing user changes, and fail without leaving a partially configured repository if validation or generation fails. Refuse to run on an already configured or unexpectedly modified template with an actionable error. Support non-interactive arguments as well as prompts so the same path is exercised in CI. A disposable-project test must exercise a hyphenated name, Cargo's underscore-normalized library identifier, and metadata containing quotes or other special characters.

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
  workflows/               # Active template CI; generated CI is manual-only
  workflow-templates/      # Publishing example outside the active workflow directory
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

The example CLI uses clap and calls a small greet function in lib.rs, demonstrating separately testable logic and argument handling. Derive help and version from Cargo metadata. Keep normal output on stdout and diagnostics on stderr, and return a nonzero status for invalid arguments. Test the executable as a user sees it: successful output, `--help`, `--version`, and invalid input, without assuming a platform-specific executable path. Explain that publishing the package also exposes its library target, which can create compatibility obligations. Retain MIT licensing, optional agent skills guidance, and OpenSpec integration; Rust builds must not depend on agent tooling. Do not add dotenv loading, async runtimes, logging frameworks, or a workspace by default.

## Toolchain and development

Pin a concrete stable Rust toolchain, including rustfmt and Clippy. Initially set Cargo's rust-version to that same version; a lower minimum becomes a support promise and must be tested separately. Commit Cargo.lock and use `--locked` for checks and builds where supported. Choose an edition supported by the pinned toolchain. Document how and when to update the toolchain and its MSRV together; CI must test the declared minimum. Keep default Cargo profiles and lint settings unless a concrete need justifies customization.

| Command | Behavior |
| --- | --- |
| `make setup` | Check prerequisites and install optional Git hooks. |
| `make check` | Non-fixing formatting, Clippy, documentation, spelling, YAML, and test checks. |
| `make format` | Apply Rust formatting and documented safe fixes. |
| `make test` | Run unit, integration, and documentation tests. |
| `make build` | Build a release binary and verify the source package. |
| `make upgrade` | Update the lockfile for review. |
| `make template-test` | Configure and verify a disposable generated project. |

Select and pin concrete spelling and YAML tools, document how to install them, and ensure setup provides or clearly verifies them. Test their availability before making them mandatory. Do not require Python after bootstrap solely to run the Rust project. Checks must not require Git hooks. Define the exact commands and tool versions in the implementation; use Clippy on all targets and features with warnings denied, and rustdoc with warnings denied. Checks may write build artifacts and caches but must not modify tracked source files. Make local checks and the corresponding CI job run the same commands.

Support the make workflow on macOS and Linux. Document equivalent Cargo commands for Windows and test Cargo builds and tests there. Do not claim full Windows make support without testing its prerequisites.

## Dependency and security policy

Enable a 14-day dependency cooling-off period only if the selected stable Cargo version supports it and an integration check verifies both the policy and an emergency override. Otherwise document the gap; do not require nightly or claim unenforced parity. Lockfile updates are deliberate and reviewed. Explain that a cooldown affects new dependency resolution, not versions already in the lockfile, and does not replace vulnerability monitoring. Exercise the policy using a controlled registry fixture rather than relying on the age of public releases.

Provide an optional RustSec audit command or scheduled workflow, separate from the default local check because advisory data changes and requires network access. Document optional coverage without imposing a universal threshold. Consider automated dependency-update proposals, but leave them opt-in and ensure they respect any enabled cooldown. Avoid adding `cargo-deny`, coverage, release automation, or a second test runner to the default toolchain without a demonstrated need.

## CI and publishing

The template repository has active CI that runs its checks and exercises generation. Generated projects receive a CI workflow with only `workflow_dispatch` enabled: it is manually runnable, not disabled. Document how to add push and pull-request triggers once the project is ready. The generated workflow runs the Unix checks and separately builds and tests with Cargo on Windows. Test the generated workflow configuration as part of template CI.

Use least-privilege GitHub Actions permissions, pin third-party actions to reviewed full commit SHAs, and document how to update them. Cache Cargo dependencies and build artifacts only if cache keys include the OS, toolchain, and lockfile; correctness must not depend on a cache hit. Keep untrusted pull-request code away from publishing credentials.

Publishing is explicitly opt-in: keep the example workflow outside `.github/workflows/` until the owner copies it there and configures it; provide instructions to enable it. Grant OIDC permissions only to the publishing job and do not store a long-lived crates.io token in the example. Cargo.toml is the version source of truth; verify that the release tag matches it before publication. Document the initial manual crates.io publication, subsequent trusted-publisher setup, and automated later releases. Document `cargo publish --dry-run --locked` and inspection of `cargo package --list` before publishing. Distinguish source installation via Cargo from downloadable prebuilt binaries, and explain that `cargo install --locked` uses the packaged lockfile. Cross-platform binary releases are deferred.

## Acceptance criteria

1. A fresh template-derived repository bootstraps with realistic metadata and a hyphenated name, without leftover project placeholders.
2. The generated project passes make check, make build, and its CLI integration test on supported Unix environments.
3. Windows CI verifies the documented Cargo build and test commands.
4. The smoke test verifies packaged crate contents and runs the generated CLI.
5. Template CI exercises the full generation path, invalid input, and failure-safe marker checks.
6. Publishing instructions cover the first manual release and later trusted releases; no publishing workflow runs until the owner enables it.
7. The selected toolchain's cooling-off support is tested and accurately documented, including the lockfile limitation and override when supported.
8. Bootstrap rejects invalid names and unexpected marker states without changing the repository; special-character metadata round-trips correctly.
9. CLI tests cover help, version, successful output, and invalid input. CI uses least privilege and the generated publishing example cannot run until explicitly installed and configured.

## Background and references

- [Original Python template](https://github.com/jlevy/simple-modern-uv)
- [Rust CLI template](https://github.com/rust-cli/cli-template) — CLI-focused starting point and the cargo-generate alternative
- [Fission Rust template](https://github.com/fission-codes/rust-template)
- [Crate Expectations](https://github.com/qkniep/crate-expectations) — CI parity, action pinning, and optional tooling ideas
- [OpenZeppelin Rust project template](https://github.com/OpenZeppelin/rust-project-template) — toolchain, edition, and MSRV alignment
- [Rust GitHub Template](https://rust-github.github.io/)
- [Cargo rust-version policy](https://doc.rust-lang.org/cargo/reference/rust-version.html)
- [Cargo packaging](https://doc.rust-lang.org/cargo/commands/cargo-package.html)
- [Cargo dependency resolution](https://doc.rust-lang.org/cargo/reference/resolver.html)
- [Cargo minimum publish age](https://doc.rust-lang.org/cargo/reference/unstable.html#min-publish-age)
- [crates.io trusted publishing announcement](https://blog.rust-lang.org/2025/07/11/crates-io-development-update-2025-07/)
