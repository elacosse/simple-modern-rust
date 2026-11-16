#!/usr/bin/env bash
set -euo pipefail

FILE_PATH="${1:-}"
if [[ -z "$FILE_PATH" || ! -f "$FILE_PATH" ]]; then
  exit 0
fi

export PATH="$HOME/.cargo/bin:$PATH"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ERRORS=""

case "$FILE_PATH" in
  *.rs)
    if command -v rustfmt >/dev/null 2>&1; then
      rustfmt --edition 2024 "$FILE_PATH" 2>/dev/null || rustfmt "$FILE_PATH" 2>/dev/null || true
    fi
    if command -v cargo >/dev/null 2>&1; then
      if ! CLIPPY_OUT=$(cd "$PROJECT_ROOT" && cargo clippy --locked --all-targets --all-features --message-format=short -- -D warnings 2>&1); then
        ERRORS+="[Cargo Clippy Error]\n$CLIPPY_OUT\n\n"
      fi
    fi
    ;;
esac

if [[ -n "$ERRORS" ]]; then
  echo -e "Automated verification failed for $FILE_PATH. Fix these errors before continuing:\n\n$ERRORS" >&2
  exit 1
fi

exit 0
