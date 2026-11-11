from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from taken.core.project import (
    is_project_config_exists,
    read_project_config,
    read_projects_state,
    resolve_layout,
    write_project_config,
)
from taken.models.config import MirrorMode, SkillsConfig, TakenConfig
from taken.models.project import ProjectConfig, ProjectSkillEntry


def _config_with_skill(hash_value: str, mode: MirrorMode | None = None) -> ProjectConfig:
    config = ProjectConfig(mirror_mode=mode)
    config.skills["alice/my-skill"] = ProjectSkillEntry(copied_at=datetime(2026, 1, 1), copied_hash=hash_value)
    return config


@pytest.mark.anyio
async def test_project__write_then_read__round_trips(tmp_path: Path) -> None:
    # Arrange
    taken_home = tmp_path / ".taken"
    project_root = tmp_path / "proj"
    project_root.mkdir()

    # Act
    write_project_config(_config_with_skill("abc", MirrorMode.COPY), project_root, taken_home)
    result = read_project_config(project_root, taken_home)

    # Assert
    assert result.mirror_mode == MirrorMode.COPY
    assert result.skills["alice/my-skill"].copied_hash == "abc"
    assert result.skills["alice/my-skill"].copied_at == datetime(2026, 1, 1)
    assert not (project_root / ".taken.yaml").exists()


@pytest.mark.anyio
async def test_project__write_second_project__first_project_preserved(tmp_path: Path) -> None:
    # Arrange
    taken_home = tmp_path / ".taken"
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    project_a.mkdir()
    project_b.mkdir()
    write_project_config(_config_with_skill("aaa"), project_a, taken_home)

    # Act
    write_project_config(_config_with_skill("bbb"), project_b, taken_home)

    # Assert
    assert read_project_config(project_a, taken_home).skills["alice/my-skill"].copied_hash == "aaa"
    assert read_project_config(project_b, taken_home).skills["alice/my-skill"].copied_hash == "bbb"


@pytest.mark.anyio
async def test_project__untracked_project__exists_false_and_empty_config(tmp_path: Path) -> None:
    # Arrange
    taken_home = tmp_path / ".taken"

    # Act
    exists = is_project_config_exists(tmp_path, taken_home)
    config = read_project_config(tmp_path, taken_home)

    # Assert
    assert exists is False
    assert config.skills == {}
    assert config.mirror_mode is None


@pytest.mark.anyio
async def test_project__write__projects_file_gitignored_once(tmp_path: Path) -> None:
    # Arrange
    taken_home = tmp_path / ".taken"
    taken_home.mkdir()
    (taken_home / ".gitignore").write_text("*.tmp")

    # Act
    write_project_config(ProjectConfig(), tmp_path, taken_home)
    write_project_config(ProjectConfig(), tmp_path, taken_home)

    # Assert
    assert (taken_home / ".gitignore").read_text() == "*.tmp\nprojects.yaml\n"


@pytest.mark.anyio
async def test_project__older_version_file__upcast_on_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange — pretend v1 stored "hash" and v2 renamed it to "copied_hash"
    taken_home = tmp_path / ".taken"
    taken_home.mkdir()
    key = str(tmp_path.resolve())
    (taken_home / "projects.yaml").write_text(
        f"version: 1\nprojects:\n  {key}:\n    skills:\n      alice/my-skill:\n"
        "        copied_at: '2026-01-01T00:00:00'\n        hash: old\n"
    )

    def _v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
        for project in data["projects"].values():
            for entry in project["skills"].values():
                entry["copied_hash"] = entry.pop("hash")
        return data

    monkeypatch.setattr("taken.core.project.CURRENT_PROJECTS_VERSION", 2)
    monkeypatch.setattr("taken.core.project._UPCASTERS", {1: _v1_to_v2})

    # Act
    state = read_projects_state(taken_home)

    # Assert
    assert state.version == 2
    assert state.projects[key].skills["alice/my-skill"].copied_hash == "old"


@pytest.mark.anyio
async def test_project__resolve_layout__project_mode_overrides_global(tmp_path: Path) -> None:
    # Arrange
    config = TakenConfig(username="alice", taken_home=tmp_path, skills=SkillsConfig(mirror_mode=MirrorMode.SYMLINK))

    # Act
    default_layout = resolve_layout(config, ProjectConfig())
    override_layout = resolve_layout(config, ProjectConfig(mirror_mode=MirrorMode.COPY))

    # Assert
    assert default_layout.mirror_mode == MirrorMode.SYMLINK
    assert override_layout.mirror_mode == MirrorMode.COPY
    assert default_layout.main_dir == ".agents/skills"
    assert default_layout.mirror_dirs == (".claude/skills",)
