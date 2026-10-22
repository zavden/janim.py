#!/usr/bin/env bash
# Create the checkout's virtual environment with Janim's pinned dependencies
# and make the checkout importable from it. PYTHON selects the interpreter.
set -euo pipefail
JANIM_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"${PYTHON:-python3.14}" -m venv "$JANIM_ROOT/.venv"
"$JANIM_ROOT/.venv/bin/python" "$JANIM_ROOT/scripts/bootstrap.py" "$JANIM_ROOT"
