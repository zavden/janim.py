#!/usr/bin/env bash
# Create the checkout's virtual environment with Janim's pinned dependencies
# and make the checkout importable from it. PYTHON selects the interpreter.
set -euo pipefail
JANIM_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"${PYTHON:-python3.14}" -m venv "$JANIM_ROOT/.venv"
"$JANIM_ROOT/.venv/bin/python" - "$JANIM_ROOT" <<'PY'
from pathlib import Path
import subprocess
import sys
import sysconfig
import tomllib

root = Path(sys.argv[1])
project = tomllib.loads((root / "pyproject.toml").read_text())
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--index-url",
        "https://pypi.org/simple",
        "--only-binary=:all:",
        "--no-deps",
        "--no-cache-dir",
        "--disable-pip-version-check",
        *project["project"]["dependencies"],
        *project["tool"]["janim"]["bootstrap"]["dependencies"],
    ],
    check=True,
)
# A source checkout, importable without a packaging step.
(Path(sysconfig.get_path("purelib")) / "janim.pth").write_text(str(root) + "\n")
PY
