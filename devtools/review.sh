#!/usr/bin/env bash
set -euo pipefail

# Preserve caller PATH precedence (so custom/test binaries win) while ensuring
# common user/Homebrew install locations are discoverable in non-login shells.
export PATH="$PATH:$HOME/.local/bin:/opt/homebrew/bin"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PYTHON_BIN=""
for candidate in "$PROJECT_ROOT/.venv/bin/python" python3 python3.14 python3.13 python3.12 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Error: Python 3.11+ is required to run devtools/review.sh." >&2
  exit 2
fi

exec "$PYTHON_BIN" "$PROJECT_ROOT/devtools/review.py" "$PROJECT_ROOT" "$@"
