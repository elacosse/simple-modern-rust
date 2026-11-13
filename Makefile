.DEFAULT_GOAL := check

.PHONY: setup check format test build upgrade template-test audit

setup:
	@command -v cargo >/dev/null || { echo 'Install Rust using rustup: https://rustup.rs/' >&2; exit 1; }
	@command -v typos >/dev/null || { echo 'Install typos-cli 1.38.1 (see development.md)' >&2; exit 1; }
	@command -v yamlfmt >/dev/null || { echo 'Install yamlfmt 0.16.0 (see development.md)' >&2; exit 1; }
	@command -v actionlint >/dev/null || { echo 'Install actionlint 1.7.7 (see development.md)' >&2; exit 1; }
	@echo 'Prerequisites found. Git hooks are optional; checks do not require them.'

check: setup
	cargo fmt --all -- --check
	cargo clippy --locked --all-targets --all-features -- -D warnings
	RUSTDOCFLAGS='-D warnings' cargo doc --locked --no-deps --all-features
	typos
	actionlint .github/workflows/*.yml .github/workflow-templates/*.yml
	yamlfmt -lint .github/workflows/*.yml .github/workflow-templates/*.yml openspec/*.yaml
	$(MAKE) test

format:
	cargo fmt --all

test:
	cargo test --locked --all-features

build:
	cargo build --release --locked
	cargo package --locked --allow-dirty

upgrade:
	cargo update

template-test:
	python3 scripts/template_test.py

audit:
	cargo audit --locked
