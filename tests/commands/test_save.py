from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.hashing import compute_skill_hash
from taken.core.project import read_project_config, write_project_config
from taken.core.registry import read_registry, write_registry
from taken.main import app
from taken.models.config import MirrorMode, TakenConfig
from taken.models.project import ProjectConfig, ProjectSkillEntry
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


@pytest.fixture
def scaffold_project_skill(tmp_path: Path) -> Callable[[str], Path]:
    """Create a skill in the project's .agents/skills/ and return its path."""

    def _inner(name: str) -> Path:
        skill_dir = tmp_path / ".agents" / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}\noriginal content")
        return skill_dir

    return _inner


@pytest.mark.anyio
async def test_save__not_initialized__exits_with_error(
    cli_runner: CliRunner,
) -> None:
    # Arrange — no config written

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Not Initialized" in result.output


@pytest.mark.anyio
async def test_save__no_project_config__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange — no .taken.yaml in cwd
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Not a Taken Project" in result.output
    assert "taken use" in result.output


@pytest.mark.anyio
async def test_save__no_tracked_skills__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange — .taken.yaml exists but has no skills
    write_config(sample_config)
    write_project_config(ProjectConfig(), tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "No Skills Tracked" in result.output
    assert "taken use" in result.output


@pytest.mark.anyio
async def test_save__explicit_skill_not_tracked__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — project tracks other-skill but not my-skill
    write_config(sample_config)
    skill_dir = scaffold_project_skill("other-skill")
    pc = ProjectConfig()
    pc.skills["alice/other-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=compute_skill_hash(skill_dir),
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Skill Not Found" in result.output
    assert "alice/my-skill" in result.output


@pytest.mark.anyio
async def test_save__skill_unchanged__skips_with_no_changes_message(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — project copy hash matches .taken.yaml baseline
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=compute_skill_hash(skill_dir),  # hash matches current state
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "No changes" in result.output
    assert "alice/my-skill" in result.output
    assert "Skills Saved" not in result.output


@pytest.mark.anyio
async def test_save__skill_modified__saved_to_registry_and_hash_updated(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — project copy was edited after `taken use`
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL, updated_at=None)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    registry_skill_dir = scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")
    original_hash = compute_skill_hash(skill_dir)

    # Edit project copy to make hash differ
    (skill_dir / "SKILL.md").write_text("# my-skill\nmodified in project")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=original_hash,  # stale — project was edited after copy
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "Skills Saved" in result.output
    assert "alice/my-skill" in result.output

    # Registry skill dir updated with project content
    assert (registry_skill_dir / "SKILL.md").read_text() == "# my-skill\nmodified in project"

    # .taken.yaml copied_hash updated to reflect new state
    updated_project_config = read_project_config(tmp_path)
    new_hash = updated_project_config.skills["alice/my-skill"].copied_hash
    assert new_hash != original_hash
    assert new_hash == compute_skill_hash(registry_skill_dir)

    # Registry updated_at stamped
    updated_registry = read_registry(taken_home)
    updated_entry = updated_registry.get("alice/my-skill")
    assert updated_entry is not None
    assert updated_entry.updated_at is not None


@pytest.mark.anyio
async def test_save__multiple_skills_mixed__saves_changed_skips_unchanged(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — skill-a modified, skill-b unchanged
    write_config(sample_config)
    entry_a = RegistryEntryFactory.build(namespace="alice", name="skill-a", source=SkillSource.PERSONAL)
    entry_b = RegistryEntryFactory.build(namespace="alice", name="skill-b", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry_a)
    registry.add(entry_b)
    write_registry(registry, taken_home)
    registry_skill_a = scaffold_registry_skill("alice", "skill-a")
    scaffold_registry_skill("alice", "skill-b")
    skill_a_dir = scaffold_project_skill("skill-a")
    skill_b_dir = scaffold_project_skill("skill-b")

    original_hash_a = compute_skill_hash(skill_a_dir)
    real_hash_b = compute_skill_hash(skill_b_dir)

    # Edit skill-a in project (hash will differ); skill-b untouched (hash matches)
    (skill_a_dir / "SKILL.md").write_text("# skill-a\nedited in project")

    pc = ProjectConfig()
    pc.skills["alice/skill-a"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=original_hash_a,
    )
    pc.skills["alice/skill-b"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=real_hash_b,
    )
    write_project_config(pc, tmp_path)

    # Invoke save for both via two direct calls (no interactive picker)
    monkeypatch.chdir(tmp_path)
    result_a = cli_runner.invoke(app, ["save", "alice/skill-a"])
    result_b = cli_runner.invoke(app, ["save", "alice/skill-b"])

    # Assert skill-a saved
    assert result_a.exit_code == 0
    assert "Skills Saved" in result_a.output
    assert "alice/skill-a" in result_a.output
    assert (registry_skill_a / "SKILL.md").read_text() == "# skill-a\nedited in project"

    # Assert skill-b skipped
    assert result_b.exit_code == 0
    assert "No changes" in result_b.output
    assert "Skills Saved" not in result_b.output

    # .taken.yaml: skill-a hash updated, skill-b hash preserved
    updated_config = read_project_config(tmp_path)
    assert updated_config.skills["alice/skill-a"].copied_hash != original_hash_a
    assert updated_config.skills["alice/skill-b"].copied_hash == real_hash_b


@pytest.mark.anyio
async def test_save__preserves_copied_at_timestamp(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")
    original_hash = compute_skill_hash(skill_dir)
    original_copied_at = datetime(2025, 1, 1, 12, 0, 0)

    (skill_dir / "SKILL.md").write_text("# my-skill\nedited")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=original_copied_at,
        copied_hash=original_hash,
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert — copied_at must not change; only copied_hash updates
    assert result.exit_code == 0
    updated_config = read_project_config(tmp_path)
    assert updated_config.skills["alice/my-skill"].copied_at == original_copied_at
    assert updated_config.skills["alice/my-skill"].copied_hash != original_hash


@pytest.mark.anyio
async def test_save__skill_not_in_registry__still_saves_files(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — skill in .taken.yaml but not in registry (e.g. registry drift)
    write_config(sample_config)
    write_registry(Registry(), taken_home)  # empty registry
    scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")
    original_hash = compute_skill_hash(skill_dir)

    (skill_dir / "SKILL.md").write_text("# my-skill\nedited")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=original_hash,
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act — should still copy files even without a registry entry
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "Skills Saved" in result.output
    registry_skill_dir = taken_home / "skills" / "alice" / "my-skill"
    assert (registry_skill_dir / "SKILL.md").read_text() == "# my-skill\nedited"


@pytest.fixture
def used_in_copy_mode(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
) -> Path:
    """alice/my-skill used into the project (cwd = tmp_path) in copy mode; returns the registry skill dir."""
    sample_config.skills.mirror_mode = MirrorMode.COPY
    write_config(sample_config)
    registry = Registry()
    registry.add(RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL))
    write_registry(registry, taken_home)
    registry_skill = scaffold_registry_skill("alice", "my-skill")
    monkeypatch.chdir(tmp_path)
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])
    assert result.exit_code == 0
    return registry_skill


@pytest.mark.anyio
async def test_save__copy_mode_only_mirror_edited__saves_mirror_and_syncs_main(
    cli_runner: CliRunner,
    tmp_path: Path,
    used_in_copy_mode: Path,
) -> None:
    # Arrange
    main = tmp_path / ".agents" / "skills" / "my-skill"
    mirror = tmp_path / ".claude" / "skills" / "my-skill"
    (mirror / "SKILL.md").write_text("# edited in claude dir")

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "Skills Saved" in result.output
    assert (used_in_copy_mode / "SKILL.md").read_text() == "# edited in claude dir"
    assert (main / "SKILL.md").read_text() == "# edited in claude dir"
    assert read_project_config(tmp_path).skills["alice/my-skill"].copied_hash == compute_skill_hash(main)


@pytest.mark.anyio
async def test_save__copy_mode_both_edited_same__saves_without_prompt(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    used_in_copy_mode: Path,
) -> None:
    # Arrange
    for d in (".agents", ".claude"):
        (tmp_path / d / "skills" / "my-skill" / "SKILL.md").write_text("# same edit")

    def _prompt_not_expected(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("should not prompt")

    monkeypatch.setattr("taken.commands.save.Prompt.ask", _prompt_not_expected)

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert (used_in_copy_mode / "SKILL.md").read_text() == "# same edit"


@pytest.mark.anyio
async def test_save__copy_mode_both_edited_differently__user_picks_copy(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    used_in_copy_mode: Path,
) -> None:
    # Arrange
    main = tmp_path / ".agents" / "skills" / "my-skill"
    mirror = tmp_path / ".claude" / "skills" / "my-skill"
    (main / "SKILL.md").write_text("# agents edit")
    (mirror / "SKILL.md").write_text("# claude edit")

    def _pick_second(*_args: object, **_kwargs: object) -> str:
        return "2"

    monkeypatch.setattr("taken.commands.save.Prompt.ask", _pick_second)

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "edited differently" in result.output
    assert (used_in_copy_mode / "SKILL.md").read_text() == "# claude edit"
    assert (main / "SKILL.md").read_text() == "# claude edit"
    assert (mirror / "SKILL.md").read_text() == "# claude edit"


@pytest.mark.anyio
async def test_save__symlink_mode_edit_through_link__saved_from_main(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
) -> None:
    # Arrange — default symlink mode; edit via the .claude link
    write_config(sample_config)
    registry = Registry()
    registry.add(RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL))
    write_registry(registry, taken_home)
    registry_skill = scaffold_registry_skill("alice", "my-skill")
    monkeypatch.chdir(tmp_path)
    cli_runner.invoke(app, ["use", "alice/my-skill"])
    mirror = tmp_path / ".claude" / "skills" / "my-skill"
    (mirror / "SKILL.md").write_text("# edited via link")

    # Act
    result = cli_runner.invoke(app, ["save", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert (registry_skill / "SKILL.md").read_text() == "# edited via link"
    assert mirror.is_symlink()
