from pathlib import Path

import pytest

import taken.core.paths as taken_paths


@pytest.fixture(autouse=True)
def patch_taken_home(taken_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taken_paths, "TAKEN_HOME", taken_home)
