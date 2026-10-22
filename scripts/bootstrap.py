"""Install Janim's pinned dependencies into the running interpreter and make
the checkout importable from it. bootstrap.sh and bootstrap.cmd run it with
the checkout's root, inside the virtual environment they just created."""
from pathlib import Path
import subprocess
import sys
import sysconfig
import tomllib

root = Path(sys.argv[1])
project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
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
(Path(sysconfig.get_path("purelib")) / "janim.pth").write_text(str(root) + "\n", encoding="utf-8")
