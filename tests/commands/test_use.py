import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.hashing import compute_skill_hash
from taken.core.project import read_project_config, write_project_config
from taken.core.registry import write_registry
from taken.main import app
from taken.models.config import TakenConfig
from taken.models.project import ProjectConfig, ProjectSkillEntry
from taken.models.registry import Registry, SkillSource
from tests.fixtures.registry import RegistryEntryFactory


def _confirm_yes(*_args: object, **_kwargs: object) -> bool:
    return True


def _confirm_no(*_args: object, **_kwargs: object) -> bool:
    return False


@pytest.fixture
def scaffold_skill(taken_home: Path) -> Callable[[str, str], Path]:
    def _inner(namespace: str, name: str) -> Path:
        skill_src = taken_home / "skills" / namespace / name
        skill_src.mkdir(parents=True)
        (skill_src / "SKILL.md").write_text(f"# {name}\noriginal content")
        (skill_src / "helper.py").write_text("def foo(): pass")
        sub = skill_src / "subdir"
        sub.mkdir()
        (sub / "extra.md").write_text("extra content")
        return skill_src

    return _inner


@pytest.mark.anyio
async def test_use__not_initialized__exits_with_error(
    cli_runner: CliRunner,
) -> None:
    # Arrange — config absent (taken_home is empty)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Not Initialized" in result.output


@pytest.mark.anyio
async def test_use__empty_registry__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Registry Empty" in result.output
    assert "taken add" in result.output


@pytest.mark.anyio
async def test_use__explicit_skill_not_in_registry__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_skill: Callable[[str, str], Path],
) -> None:
    # Arrange — registry has other-skill but not my-skill
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="other-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    scaffold_skill("alice", "other-skill")
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Skill Not Found" in result.output
    assert "alice/my-skill" in result.output
    assert "taken list" in result.output


@pytest.mark.anyio
async def test_use__explicit_skill__copied_to_project_and_tracked(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_skill: Callable[[str, str], Path],
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    skill_src = scaffold_skill("alice", "my-skill")
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "Skills Added" in result.output
    assert "alice/my-skill" in result.output

    dst = tmp_path / ".agents" / "skills" / "my-skill"
    assert dst.is_dir()
    assert (dst / "SKILL.md").exists()
    assert (dst / "helper.py").exists()
    assert (dst / "subdir" / "extra.md").exists()
    assert (dst / "SKILL.md").read_text() == (skill_src / "SKILL.md").read_text()
    assert (dst / "helper.py").read_text() == "def foo(): pass"
    assert (dst / "subdir" / "extra.md").read_text() == "extra content"

    assert (tmp_path / ".taken.yaml").exists()
    project_config = read_project_config(tmp_path)
    assert project_config.version == 1
    assert project_config.skills_dir == ".agents/skills"
    assert "alice/my-skill" in project_config.skills
    skill_entry = project_config.skills["alice/my-skill"]
    assert skill_entry.copied_hash != ""
    assert skill_entry.copied_hash == compute_skill_hash(dst)
    assert skill_entry.copied_at is not None


@pytest.mark.anyio
async def test_use__local_changes_user_confirms__skill_overwritten(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_skill: Callable[[str, str], Path],
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    skill_src = scaffold_skill("alice", "my-skill")
    monkeypatch.chdir(tmp_path)

    # Simulate a previous copy with local edits (stale hash)
    dst = tmp_path / ".agents" / "skills" / "my-skill"
    shutil.copytree(skill_src, dst)
    (dst / "SKILL.md").write_text("# locally modified")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash="stale_hash_doesnt_match",
    )
    write_project_config(pc, tmp_path)

    monkeypatch.setattr("taken.commands.use.Confirm.ask", _confirm_yes)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "local changes" in result.output
    assert "Skills Added" in result.output
    assert (dst / "SKILL.md").read_text() == (skill_src / "SKILL.md").read_text()
    updated_config = read_project_config(tmp_path)
    assert updated_config.skills["alice/my-skill"].copied_hash != "stale_hash_doesnt_match"


@pytest.mark.anyio
async def test_use__local_changes_user_declines__skill_skipped(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_skill: Callable[[str, str], Path],
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    skill_src = scaffold_skill("alice", "my-skill")
    monkeypatch.chdir(tmp_path)

    # Simulate a previous copy with local edits (stale hash)
    dst = tmp_path / ".agents" / "skills" / "my-skill"
    shutil.copytree(skill_src, dst)
    (dst / "SKILL.md").write_text("# locally modified")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash="stale_hash_doesnt_match",
    )
    write_project_config(pc, tmp_path)

    monkeypatch.setattr("taken.commands.use.Confirm.ask", _confirm_no)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "local changes" in result.output
    assert "Skipped" in result.output
    assert "alice/my-skill" in result.output
    assert "Skills Added" not in result.output
    assert (dst / "SKILL.md").read_text() == "# locally modified"
    assert read_project_config(tmp_path).skills["alice/my-skill"].copied_hash == "stale_hash_doesnt_match"


@pytest.mark.anyio
async def test_use__no_local_changes__overwrites_without_prompt(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_skill: Callable[[str, str], Path],
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    skill_src = scaffold_skill("alice", "my-skill")
    monkeypatch.chdir(tmp_path)

    # Simulate a previous copy with matching hash (no local changes)
    dst = tmp_path / ".agents" / "skills" / "my-skill"
    shutil.copytree(skill_src, dst)
    real_hash = compute_skill_hash(dst)

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=real_hash,
    )
    write_project_config(pc, tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "local changes" not in result.output
    assert "Skills Added" in result.output
    assert (dst / "SKILL.md").read_text() == (skill_src / "SKILL.md").read_text()


@pytest.mark.anyio
async def test_use__add_new_skill__existing_tracked_skills_preserved(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_skill: Callable[[str, str], Path],
) -> None:
    # Arrange — two skills; skill-a already tracked, use only skill-b
    write_config(sample_config)
    entry_a = RegistryEntryFactory.build(namespace="alice", name="skill-a", source=SkillSource.PERSONAL)
    entry_b = RegistryEntryFactory.build(namespace="alice", name="skill-b", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry_a)
    registry.add(entry_b)
    write_registry(registry, taken_home)
    scaffold_skill("alice", "skill-a")
    scaffold_skill("alice", "skill-b")
    monkeypatch.chdir(tmp_path)

    # Pre-write .taken.yaml as if skill-a was already used
    pc = ProjectConfig()
    pc.skills["alice/skill-a"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash="existing_hash",
    )
    write_project_config(pc, tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/skill-b"])

    # Assert
    assert result.exit_code == 0
    assert "alice/skill-b" in result.output
    assert (tmp_path / ".agents" / "skills" / "skill-b").is_dir()

    project_config = read_project_config(tmp_path)
    assert "alice/skill-a" in project_config.skills
    assert "alice/skill-b" in project_config.skills
    assert project_config.skills["alice/skill-a"].copied_hash == "existing_hash"
