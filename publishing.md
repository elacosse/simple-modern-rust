# Publishing

Publication is opt-in. Check that the crate name is available on crates.io and review package metadata, the changelog, and `cargo package --list`. Run `cargo publish --dry-run --locked` before releasing. Cargo.toml is the version source of truth; release tags use `v` followed by that exact version.

For the first release, authenticate locally with `cargo login` and run `cargo publish --locked`. Follow the current [crates.io trusted publishing documentation](https://crates.io/docs/trusted-publishing) to configure a trusted publisher for subsequent releases. Copy `.github/workflow-templates/publish.yml` into `.github/workflows/`, configure the trusted publisher for that workflow and repository, and review its permissions before creating a matching tag. The workflow uses OIDC; it needs no long-lived crates.io token. Configure repository protections as appropriate.

The generated CI workflow is manually runnable via Actions. Add `push` and `pull_request` triggers after reviewing the project. This project publishes source through Cargo; cross-platform prebuilt binaries are not provided.
