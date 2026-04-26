import os
import shlex
import subprocess
from pathlib import Path


def open_in_editor(path: Path) -> None:
    """Open path in the user's preferred editor, blocking until closed.

    Detection order: $VISUAL → $EDITOR → vim.
    """
    raw = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"
    argv = shlex.split(raw) + [str(path)]
    subprocess.run(argv)
