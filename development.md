# Development

Install Rust through [rustup](https://rustup.rs/), GNU Make, Git, and the pinned tools `typos-cli` 1.38.1, `actionlint` 1.7.7, and `yamlfmt` 0.16.0. Install typos with `cargo install typos-cli --version 1.38.1 --locked`; obtain the matching actionlint binary from its [releases](https://github.com/rhysd/actionlint/releases/tag/v1.7.7). Obtain yamlfmt from its [releases](https://github.com/google/yamlfmt/releases/tag/v0.16.0). Put all three on PATH. `make setup` verifies they are available; hooks are optional.

On macOS and Linux, use `make check`, `make format`, `make test`, `make build`, and `make upgrade`. Checks may create build artifacts but do not fix tracked files. `make upgrade` updates Cargo.lock for review. The template maintainer can use `make template-test` to exercise bootstrap.

On Windows, use `cargo fmt --all -- --check`, `cargo clippy --locked --all-targets --all-features -- -D warnings`, `cargo test --locked --all-features`, and `cargo build --release --locked`. Windows Make and the extra checks are not supported without separately installing their prerequisites.

The pinned toolchain and `rust-version` are initially the same. Update both deliberately, regenerate and review Cargo.lock, and run CI. Supporting an older minimum Rust version requires testing that version separately.

The pinned stable Cargo does not enforce a dependency cooldown. Review lockfile updates and consider the optional `make audit` (install `cargo-audit` first); advisory data changes and requires network access. A future cooldown would apply to new resolution, not already locked versions, and would not replace advisory monitoring.
