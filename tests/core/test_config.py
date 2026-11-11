from pathlib import Path

import pytest

from taken.core.config import read_config, write_config
from taken.models.config import MirrorMode, SkillsConfig, TakenConfig


@pytest.mark.anyio
async def test_config__old_file_without_skills_key__uses_defaults(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "config.yaml").write_text("version: '1'\nusername: alice\n")

    # Act
    config = read_config(tmp_path)

    # Assert
    assert config.skills == SkillsConfig()
    assert config.skills.mirror_mode == MirrorMode.SYMLINK


@pytest.mark.anyio
async def test_config__skills_settings__round_trip(tmp_path: Path) -> None:
    # Arrange
    skills = SkillsConfig(
        main_dir="skills", mirror_dirs=[".claude/skills", ".cursor/skills"], mirror_mode=MirrorMode.COPY
    )
    config = TakenConfig(username="alice", taken_home=tmp_path, skills=skills)

    # Act
    write_config(config)
    result = read_config(tmp_path)

    # Assert
    assert result.skills == skills
