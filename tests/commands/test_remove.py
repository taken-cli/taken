from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.registry import read_registry, write_registry
from taken.main import app
from taken.models.config import TakenConfig
from taken.models.registry import Registry, SkillSource
from tests.fixtures.registry import RegistryEntryFactory


@pytest.fixture
def scaffold_registry_skill(taken_home: Path) -> Callable[[str, str], Path]:
    """Create a skill in ~/.taken/skills/ and return its path."""

    def _inner(namespace: str, name: str) -> Path:
        skill_dir = taken_home / "skills" / namespace / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}\noriginal content")
        return skill_dir

    return _inner


@pytest.mark.anyio
async def test_remove__not_initialized__exits_with_error(
    cli_runner: CliRunner,
) -> None:
    # Arrange — no config written

    # Act
    result = cli_runner.invoke(app, ["remove", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Not Initialized" in result.output


@pytest.mark.anyio
async def test_remove__empty_registry__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)

    # Act
    result = cli_runner.invoke(app, ["remove", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Registry Empty" in result.output


@pytest.mark.anyio
async def test_remove__explicit_skill_not_in_registry__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    scaffold_registry_skill: Callable[[str, str], Path],
) -> None:
    # Arrange — registry has other-skill, not my-skill
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="other-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    scaffold_registry_skill("alice", "other-skill")

    # Act
    result = cli_runner.invoke(app, ["remove", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Skill Not Found" in result.output
    assert "alice/my-skill" in result.output


@pytest.mark.anyio
async def test_remove__explicit_skill_confirm_yes__removed_from_registry_and_filesystem(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    scaffold_registry_skill: Callable[[str, str], Path],
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    skill_dir = scaffold_registry_skill("alice", "my-skill")

    # Act
    result = cli_runner.invoke(app, ["remove", "alice/my-skill"], input="y\n")

    # Assert
    assert result.exit_code == 0
    assert "Skills Removed" in result.output
    assert "alice/my-skill" in result.output
    assert "unaffected" in result.output

    updated_registry = read_registry(taken_home)
    assert updated_registry.get("alice/my-skill") is None
    assert not skill_dir.exists()


@pytest.mark.anyio
async def test_remove__explicit_skill_confirm_no__skipped(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    scaffold_registry_skill: Callable[[str, str], Path],
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    skill_dir = scaffold_registry_skill("alice", "my-skill")

    # Act
    result = cli_runner.invoke(app, ["remove", "alice/my-skill"], input="n\n")

    # Assert
    assert result.exit_code == 0
    assert "Skills Removed" not in result.output
    assert "No skills removed" in result.output

    updated_registry = read_registry(taken_home)
    assert updated_registry.get("alice/my-skill") is not None
    assert skill_dir.exists()


@pytest.mark.anyio
async def test_remove__skill_folder_missing__still_removes_from_registry(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange — skill in registry but folder was manually deleted
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    # intentionally do NOT create the skill dir

    # Act
    result = cli_runner.invoke(app, ["remove", "alice/my-skill"], input="y\n")

    # Assert — no crash, registry cleaned up
    assert result.exit_code == 0
    assert "Skills Removed" in result.output

    updated_registry = read_registry(taken_home)
    assert updated_registry.get("alice/my-skill") is None


@pytest.mark.anyio
async def test_remove__multiple_skills_partial_confirm__correct_state(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    scaffold_registry_skill: Callable[[str, str], Path],
) -> None:
    # Arrange — skill-a confirmed, skill-b declined
    write_config(sample_config)
    entry_a = RegistryEntryFactory.build(namespace="alice", name="skill-a", source=SkillSource.PERSONAL)
    entry_b = RegistryEntryFactory.build(namespace="alice", name="skill-b", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry_a)
    registry.add(entry_b)
    write_registry(registry, taken_home)
    skill_a_dir = scaffold_registry_skill("alice", "skill-a")
    skill_b_dir = scaffold_registry_skill("alice", "skill-b")

    result_a = cli_runner.invoke(app, ["remove", "alice/skill-a"], input="y\n")
    result_b = cli_runner.invoke(app, ["remove", "alice/skill-b"], input="n\n")

    # Assert skill-a removed
    assert result_a.exit_code == 0
    assert "Skills Removed" in result_a.output
    assert not skill_a_dir.exists()

    # Assert skill-b skipped
    assert result_b.exit_code == 0
    assert "No skills removed" in result_b.output
    assert skill_b_dir.exists()

    updated_registry = read_registry(taken_home)
    assert updated_registry.get("alice/skill-a") is None
    assert updated_registry.get("alice/skill-b") is not None
