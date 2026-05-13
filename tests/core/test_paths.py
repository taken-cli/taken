import importlib
from pathlib import Path

import pytest

import taken.core.paths as taken_paths


@pytest.mark.anyio
async def test_paths__no_env_var__defaults_to_home_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("TAKEN_HOME", raising=False)

    # Act
    importlib.reload(taken_paths)

    # Assert
    assert Path.home() / ".taken" == taken_paths.TAKEN_HOME


@pytest.mark.anyio
async def test_paths__env_var_set__uses_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Arrange
    monkeypatch.setenv("TAKEN_HOME", str(tmp_path))

    # Act
    importlib.reload(taken_paths)

    # Assert
    assert tmp_path == taken_paths.TAKEN_HOME
