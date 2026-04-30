import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.registry import read_registry, write_registry
from taken.main import app
from taken.models.config import TakenConfig
from taken.models.registry import Registry, SkillSource
from tests.fixtures.registry import RegistryEntryFactory


def _noop_editor(path: Path) -> None:
    pass


def _always_is_path(_arg: str) -> bool:
    return True


@pytest.mark.anyio
async def test_add__not_initialized__exits_with_error(
    cli_runner: CliRunner,
) -> None:
    # Arrange — config absent (taken_home is empty)

    # Act
    result = cli_runner.invoke(app, ["add", "my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Not Initialized" in result.output


@pytest.mark.anyio
async def test_add__create_valid_skill__skill_scaffolded_and_registered(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)
    monkeypatch.setattr("taken.commands.add.open_in_editor", _noop_editor)

    # Act
    result = cli_runner.invoke(app, ["add", "my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "Skill Created" in result.output
    assert "my-skill" in result.output

    skill_dir = taken_home / "skills" / sample_config.username / "my-skill"
    assert skill_dir.is_dir()

    skill_md = skill_dir / "SKILL.md"
    assert skill_md.exists()
    content = skill_md.read_text()
    assert "name: my-skill" in content
    assert "Write your skill instructions here" in content

    registry = read_registry(taken_home)
    full_name = f"{sample_config.username}/my-skill"
    assert registry.exists(full_name)
    entry = registry.get(full_name)
    assert entry is not None
    assert entry.source == SkillSource.PERSONAL
    assert entry.version == "1"
    assert entry.namespace == sample_config.username
    assert entry.created_at is not None


@pytest.mark.anyio
async def test_add__create_name_with_slash__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)
    monkeypatch.setattr("taken.commands.add.open_in_editor", _noop_editor)

    # Act
    result = cli_runner.invoke(app, ["add", "namespace/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Invalid Skill Name" in result.output
    assert "namespace" in result.output
    assert read_registry(taken_home).skills == {}


@pytest.mark.anyio
async def test_add__create_name_with_invalid_chars__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)
    monkeypatch.setattr("taken.commands.add.open_in_editor", _noop_editor)

    # Act
    result1 = cli_runner.invoke(app, ["add", "!bad"])
    result2 = cli_runner.invoke(app, ["add", "bad!name"])

    # Assert
    assert result1.exit_code == 1
    assert "Invalid Skill Name" in result1.output
    assert result2.exit_code == 1
    assert "Invalid Skill Name" in result2.output
    assert read_registry(taken_home).skills == {}


@pytest.mark.anyio
async def test_add__create_duplicate_skill__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace=sample_config.username, name="my-skill")
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    monkeypatch.setattr("taken.commands.add.open_in_editor", _noop_editor)

    # Act
    result = cli_runner.invoke(app, ["add", "my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Already Exists" in result.output
    assert len(read_registry(taken_home).skills) == 1


@pytest.mark.anyio
async def test_add__create_skill_directory_conflict__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)
    (taken_home / "skills" / sample_config.username / "conflict-skill").mkdir(parents=True)
    monkeypatch.setattr("taken.commands.add.open_in_editor", _noop_editor)

    # Act
    result = cli_runner.invoke(app, ["add", "conflict-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Directory Conflict" in result.output
    assert "taken doctor" in result.output
    assert read_registry(taken_home).skills == {}


@pytest.mark.anyio
async def test_add__adopt_directory_no_lock__personal_entry_registered(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)

    source_dir = tmp_path / "adopted-skill"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("# Adopted skill")

    monkeypatch.chdir(tmp_path)  # no skills-lock.json here → lookup_lock_entry returns None

    # Act
    result = cli_runner.invoke(app, ["add", str(source_dir)])

    # Assert
    assert result.exit_code == 0
    assert "Skill Adopted" in result.output

    dest_dir = taken_home / "skills" / sample_config.username / "adopted-skill"
    assert dest_dir.is_dir()
    assert (dest_dir / "SKILL.md").exists()

    registry = read_registry(taken_home)
    full_name = f"{sample_config.username}/adopted-skill"
    assert registry.exists(full_name)
    entry = registry.get(full_name)
    assert entry is not None
    assert entry.source == SkillSource.PERSONAL
    assert entry.repo is None
    assert entry.installed_at is None
    assert entry.created_at is not None


@pytest.mark.anyio
async def test_add__adopt_directory_with_lock_entry__npx_entry_registered(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)

    source_dir = tmp_path / "cool-skill"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("# Cool skill")

    lock_data = {
        "skills": {
            "cool-skill": {
                "source": "acme-org/agent-skills",
                "sourceType": "github",
                "ref": "abc1234",
            }
        }
    }
    (tmp_path / "skills-lock.json").write_text(json.dumps(lock_data))

    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["add", str(source_dir)])

    # Assert
    assert result.exit_code == 0
    assert "Skill Adopted" in result.output

    dest_dir = taken_home / "skills" / "acme-org" / "cool-skill"
    assert dest_dir.is_dir()

    registry = read_registry(taken_home)
    assert registry.exists("acme-org/cool-skill")
    entry = registry.get("acme-org/cool-skill")
    assert entry is not None
    assert entry.source == SkillSource.NPX
    assert entry.namespace == "acme-org"
    assert entry.repo == "acme-org/agent-skills"
    assert entry.version == "abc1234"
    assert entry.installed_at is not None
    assert entry.created_at is None


@pytest.mark.anyio
async def test_add__adopt_non_directory_path__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)
    # Force adopt mode on a path that doesn't exist as a directory
    monkeypatch.setattr("taken.commands.add.is_path_argument", _always_is_path)

    # Act
    result = cli_runner.invoke(app, ["add", "/tmp/nonexistent_xyz_abc_taken_test"])

    # Assert
    assert result.exit_code == 1
    assert "Invalid Path" in result.output
    assert "not a directory" in result.output
    assert read_registry(taken_home).skills == {}


@pytest.mark.anyio
async def test_add__adopt_duplicate_skill__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace=sample_config.username, name="existing-skill")
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)

    source_dir = tmp_path / "existing-skill"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("# Existing")

    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["add", str(source_dir)])

    # Assert
    assert result.exit_code == 1
    assert "Already Exists" in result.output
    assert len(read_registry(taken_home).skills) == 1
