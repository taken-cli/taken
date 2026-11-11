import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.hashing import compute_skill_hash
from taken.core.project import read_project_config, read_projects_state, write_project_config
from taken.core.registry import write_registry
from taken.main import app
from taken.models.config import MirrorMode, TakenConfig
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

    assert not (tmp_path / ".taken.yaml").exists()
    assert (taken_home / "projects.yaml").exists()
    project_config = read_project_config(tmp_path)
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


@pytest.fixture
def registry_with_skill(
    taken_home: Path,
    scaffold_skill: Callable[[str, str], Path],
) -> Path:
    """Registry containing alice/my-skill; returns the registry skill directory."""
    registry = Registry()
    registry.add(RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL))
    write_registry(registry, taken_home)
    return scaffold_skill("alice", "my-skill")


@pytest.mark.anyio
async def test_use__default_symlink_mode__claude_dir_is_relative_symlink(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry_with_skill: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    main = tmp_path / ".agents" / "skills" / "my-skill"
    mirror = tmp_path / ".claude" / "skills" / "my-skill"
    assert mirror.is_symlink()
    assert not mirror.readlink().is_absolute()
    assert mirror.resolve() == main.resolve()
    assert (mirror / "SKILL.md").read_text() == (registry_with_skill / "SKILL.md").read_text()


@pytest.mark.anyio
async def test_use__mode_copy_flag__claude_dir_is_real_copy_and_mode_remembered(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry_with_skill: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill", "--mode", "copy"])

    # Assert
    assert result.exit_code == 0
    mirror = tmp_path / ".claude" / "skills" / "my-skill"
    assert mirror.is_dir()
    assert not mirror.is_symlink()
    assert compute_skill_hash(mirror) == compute_skill_hash(registry_with_skill)
    assert read_project_config(tmp_path).mirror_mode == MirrorMode.COPY


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__global_copy_mode__claude_dir_is_real_copy(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    sample_config.skills.mirror_mode = MirrorMode.COPY
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    mirror = tmp_path / ".claude" / "skills" / "my-skill"
    assert mirror.is_dir()
    assert not mirror.is_symlink()
    assert read_project_config(tmp_path).mirror_mode is None


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__custom_mirror_dirs__mirrors_to_each_dir(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    sample_config.skills.mirror_dirs = [".claude/skills", ".cursor/skills"]
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert (tmp_path / ".claude" / "skills" / "my-skill").is_symlink()
    assert (tmp_path / ".cursor" / "skills" / "my-skill").is_symlink()


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__symlink_fails__falls_back_to_copy_with_warning(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    def _symlink_denied(*_args: object, **_kwargs: object) -> None:
        raise OSError("symlinks not permitted")

    monkeypatch.setattr(Path, "symlink_to", _symlink_denied)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "symlink not permitted" in result.output
    mirror = tmp_path / ".claude" / "skills" / "my-skill"
    assert mirror.is_dir()
    assert not mirror.is_symlink()


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__untracked_mirror_dir_exists_user_declines__skipped_and_preserved(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange — a hand-made .claude/skills/my-skill taken never created
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)
    foreign = tmp_path / ".claude" / "skills" / "my-skill"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("# hand written")
    monkeypatch.setattr("taken.commands.use.Confirm.ask", _confirm_no)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "not created by taken" in result.output
    assert "Skipped" in result.output
    assert (foreign / "SKILL.md").read_text() == "# hand written"
    assert not (tmp_path / ".agents" / "skills" / "my-skill").exists()


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__copy_mode_mirror_edited__prompts_before_overwrite(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange — skill already used in copy mode, then edited only in .claude
    sample_config.skills.mirror_mode = MirrorMode.COPY
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)
    cli_runner.invoke(app, ["use", "alice/my-skill"])
    mirror = tmp_path / ".claude" / "skills" / "my-skill"
    (mirror / "SKILL.md").write_text("# edited in claude dir")
    monkeypatch.setattr("taken.commands.use.Confirm.ask", _confirm_no)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert "local changes" in result.output
    assert "Skipped" in result.output
    assert (mirror / "SKILL.md").read_text() == "# edited in claude dir"


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__two_projects__tracked_separately_in_taken_home(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()

    # Act
    monkeypatch.chdir(project_a)
    cli_runner.invoke(app, ["use", "alice/my-skill"])
    monkeypatch.chdir(project_b)
    cli_runner.invoke(app, ["use", "alice/my-skill", "--mode", "copy"])

    # Assert
    state = read_projects_state(taken_home)
    assert set(state.projects) == {str(project_a.resolve()), str(project_b.resolve())}
    assert state.projects[str(project_a.resolve())].mirror_mode is None
    assert state.projects[str(project_b.resolve())].mirror_mode == MirrorMode.COPY
    assert not (project_a / ".taken.yaml").exists()
    assert not (project_b / ".taken.yaml").exists()


class _FakePrompt:
    def __init__(self, answer: list[str]) -> None:
        self.answer = answer

    def execute(self) -> list[str]:
        return self.answer


def _fake_checkbox(answer: list[str], captured: dict[str, object]) -> Callable[..., _FakePrompt]:
    def _inner(**kwargs: object) -> _FakePrompt:
        captured.update(kwargs)
        return _FakePrompt(answer)

    return _inner


def _always_interactive() -> bool:
    return True


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__interactive_picker__links_only_chosen_dirs_and_shows_them(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    sample_config.skills.mirror_dirs = [".claude/skills", ".cursor/skills"]
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr("taken.commands.use._is_interactive", _always_interactive)
    monkeypatch.setattr("taken.commands.use.inquirer.checkbox", _fake_checkbox([".cursor/skills"], captured))

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert [c.enabled for c in captured["choices"]] == [True, True]  # type: ignore[attr-defined]
    assert (tmp_path / ".cursor" / "skills" / "my-skill").is_symlink()
    assert not (tmp_path / ".claude" / "skills" / "my-skill").exists()
    assert "🔗 .cursor/skills/my-skill" in result.output
    assert read_project_config(tmp_path).skills["alice/my-skill"].mirror_dirs == [".cursor/skills"]


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__reuse_and_untick_dir__preselects_previous_and_removes_link(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange — first use links into .claude only
    sample_config.skills.mirror_dirs = [".claude/skills", ".cursor/skills"]
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)
    cli_runner.invoke(app, ["use", "alice/my-skill", "--mirror", ".claude/skills"])
    captured: dict[str, object] = {}
    monkeypatch.setattr("taken.commands.use._is_interactive", _always_interactive)
    monkeypatch.setattr("taken.commands.use.inquirer.checkbox", _fake_checkbox([".cursor/skills"], captured))

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert [c.enabled for c in captured["choices"]] == [True, False]  # type: ignore[attr-defined]
    assert not (tmp_path / ".claude" / "skills" / "my-skill").exists()
    assert (tmp_path / ".cursor" / "skills" / "my-skill").is_symlink()
    assert "removed .claude/skills/my-skill" in result.output


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__no_mirror_flag__only_main_copy(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill", "--no-mirror"])

    # Assert
    assert result.exit_code == 0
    assert (tmp_path / ".agents" / "skills" / "my-skill").is_dir()
    assert not (tmp_path / ".claude").exists()
    assert "not mirrored" in result.output
    assert read_project_config(tmp_path).skills["alice/my-skill"].mirror_dirs == []


@pytest.mark.anyio
@pytest.mark.usefixtures("registry_with_skill")
async def test_use__mirror_flag_not_in_list__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["use", "alice/my-skill", "--mirror", ".cursor/skills/"])

    # Assert
    assert result.exit_code == 1
    assert "Unknown Mirror Dir" in result.output
    assert "taken mirrors add .cursor/skills" in result.output
    assert not (tmp_path / ".agents").exists()
