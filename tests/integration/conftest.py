import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def taken_home(tmp_path: Path) -> Path:
    home = tmp_path / ".taken"
    home.mkdir()
    return home


@pytest.fixture
def taken_env(taken_home: Path) -> dict[str, str]:
    return {
        **os.environ,
        "TAKEN_HOME": str(taken_home),
        "EDITOR": "true",
        "VISUAL": "true",
    }


@pytest.fixture
def run(taken_env: dict[str, str]) -> Callable[..., subprocess.CompletedProcess[str]]:
    def _run(
        cmd: list[str],
        cwd: Path | None = None,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, env=taken_env, cwd=cwd, input=input, text=True, capture_output=True)

    return _run
