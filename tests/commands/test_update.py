from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.github import GitHubSkill
from taken.core.hashing import compute_skill_hash
from taken.core.project import read_project_config, write_project_config
from taken.core.registry import read_registry, write_registry
from taken.main import app
from taken.models.config import TakenConfig
from taken.models.project import ProjectConfig, ProjectSkillEntry
from taken.models.registry import Registry, SkillSource, VersionPin
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


def _always_confirm(prompt: str, default: bool = False) -> bool:  # noqa: ARG001
    return True


def _never_confirm(prompt: str, default: bool = False) -> bool:  # noqa: ARG001
    return False


@pytest.mark.anyio
async def test_update__not_initialized__exits_with_error(
    cli_runner: CliRunner,
) -> None:
    # Arrange — no config written

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Not Initialized" in result.output


@pytest.mark.anyio
async def test_update__no_project_config__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange — no .taken.yaml in cwd
    write_config(sample_config)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Not a Taken Project" in result.output
    assert "taken use" in result.output


@pytest.mark.anyio
async def test_update__no_tracked_skills__exits_with_error(
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
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "No Skills Tracked" in result.output
    assert "taken use" in result.output


@pytest.mark.anyio
async def test_update__explicit_skill_not_tracked__exits_with_error(
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
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Skill Not Found" in result.output
    assert "alice/my-skill" in result.output


@pytest.mark.anyio
async def test_update__already_up_to_date__skips_with_notice(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — registry and project both match copied_hash (no changes anywhere)
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    registry_dir = scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")

    # Make project and registry identical so both hashes equal copied_hash
    (skill_dir / "SKILL.md").write_text((registry_dir / "SKILL.md").read_text())
    baseline_hash = compute_skill_hash(skill_dir)

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=baseline_hash,
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "Already up to date" in result.output
    assert "alice/my-skill" in result.output
    assert "Skills Updated" not in result.output


@pytest.mark.anyio
async def test_update__registry_changed_no_local_edits__updates_and_hash_refreshed(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — registry was edited after use; project copy untouched
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    registry_dir = scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")
    baseline_hash = compute_skill_hash(skill_dir)

    # Edit registry skill after use (simulate upstream change)
    (registry_dir / "SKILL.md").write_text("# my-skill\nupdated in registry")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=baseline_hash,  # stale — registry was edited after copy
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "Skills Updated" in result.output
    assert "alice/my-skill" in result.output

    # Project copy updated with registry content
    assert skill_dir.exists()
    assert (skill_dir / "SKILL.md").read_text() == "# my-skill\nupdated in registry"

    # .taken.yaml copied_hash refreshed
    updated_config = read_project_config(tmp_path)
    new_hash = updated_config.skills["alice/my-skill"].copied_hash
    assert new_hash != baseline_hash
    assert new_hash == compute_skill_hash(skill_dir)


@pytest.mark.anyio
async def test_update__registry_changed_local_edits_user_confirms__overwrites(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — both registry and project edited since use; user confirms overwrite
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    registry_dir = scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")
    baseline_hash = compute_skill_hash(skill_dir)

    (registry_dir / "SKILL.md").write_text("# my-skill\nupdated in registry")
    (skill_dir / "SKILL.md").write_text("# my-skill\nlocal edits")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=baseline_hash,
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("taken.commands.update.Confirm.ask", _always_confirm)

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert
    assert result.exit_code == 0
    assert "Skills Updated" in result.output
    assert (skill_dir / "SKILL.md").read_text() == "# my-skill\nupdated in registry"
    updated_config = read_project_config(tmp_path)
    assert updated_config.skills["alice/my-skill"].copied_hash != baseline_hash


@pytest.mark.anyio
async def test_update__registry_changed_local_edits_user_declines__skill_skipped(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — both edited; user declines overwrite
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    registry_dir = scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")
    baseline_hash = compute_skill_hash(skill_dir)

    (registry_dir / "SKILL.md").write_text("# my-skill\nupdated in registry")
    (skill_dir / "SKILL.md").write_text("# my-skill\nlocal edits")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=baseline_hash,
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("taken.commands.update.Confirm.ask", _never_confirm)

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert — project copy unchanged, hash not updated
    assert result.exit_code == 0
    assert "Skipped" in result.output
    assert (skill_dir / "SKILL.md").read_text() == "# my-skill\nlocal edits"
    updated_config = read_project_config(tmp_path)
    assert updated_config.skills["alice/my-skill"].copied_hash == baseline_hash


@pytest.mark.anyio
async def test_update__local_edits_no_registry_change__suggests_save(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — project edited but registry unchanged since use
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    registry_dir = scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")

    # Make registry and project identical at baseline
    (skill_dir / "SKILL.md").write_text((registry_dir / "SKILL.md").read_text())
    baseline_hash = compute_skill_hash(skill_dir)

    # Edit only the project copy
    (skill_dir / "SKILL.md").write_text("# my-skill\nlocal edits only")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=baseline_hash,
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert — hint to use taken save; project untouched
    assert result.exit_code == 0
    assert "taken save" in result.output
    assert "Skills Updated" not in result.output
    assert (skill_dir / "SKILL.md").read_text() == "# my-skill\nlocal edits only"


@pytest.mark.anyio
async def test_update__multiple_skills_mixed__updates_changed_skips_unchanged(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — skill-a has registry update; skill-b is up to date
    write_config(sample_config)
    entry_a = RegistryEntryFactory.build(namespace="alice", name="skill-a", source=SkillSource.PERSONAL)
    entry_b = RegistryEntryFactory.build(namespace="alice", name="skill-b", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry_a)
    registry.add(entry_b)
    write_registry(registry, taken_home)

    registry_a = scaffold_registry_skill("alice", "skill-a")
    registry_b = scaffold_registry_skill("alice", "skill-b")
    skill_a = scaffold_project_skill("skill-a")
    skill_b = scaffold_project_skill("skill-b")

    # Make skill-b identical everywhere (up to date)
    (skill_b / "SKILL.md").write_text((registry_b / "SKILL.md").read_text())
    hash_a = compute_skill_hash(skill_a)
    hash_b = compute_skill_hash(skill_b)

    # Update registry for skill-a after baseline
    (registry_a / "SKILL.md").write_text("# skill-a\nupdated in registry")

    pc = ProjectConfig()
    pc.skills["alice/skill-a"] = ProjectSkillEntry(copied_at=datetime.now(), copied_hash=hash_a)
    pc.skills["alice/skill-b"] = ProjectSkillEntry(copied_at=datetime.now(), copied_hash=hash_b)
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act — invoke individually (no interactive picker)
    result_a = cli_runner.invoke(app, ["update", "alice/skill-a"])
    result_b = cli_runner.invoke(app, ["update", "alice/skill-b"])

    # Assert skill-a updated
    assert result_a.exit_code == 0
    assert "Skills Updated" in result_a.output
    assert (skill_a / "SKILL.md").read_text() == "# skill-a\nupdated in registry"

    # Assert skill-b skipped as up to date
    assert result_b.exit_code == 0
    assert "Already up to date" in result_b.output
    assert "Skills Updated" not in result_b.output

    # skill-a hash updated, skill-b hash unchanged
    updated_config = read_project_config(tmp_path)
    assert updated_config.skills["alice/skill-a"].copied_hash != hash_a
    assert updated_config.skills["alice/skill-b"].copied_hash == hash_b


@pytest.mark.anyio
async def test_update__preserves_copied_at_timestamp(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — registry changed; verify copied_at is not touched after update
    write_config(sample_config)
    entry = RegistryEntryFactory.build(namespace="alice", name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    registry_dir = scaffold_registry_skill("alice", "my-skill")
    skill_dir = scaffold_project_skill("my-skill")
    baseline_hash = compute_skill_hash(skill_dir)
    original_copied_at = datetime(2025, 1, 1, 12, 0, 0)

    (registry_dir / "SKILL.md").write_text("# my-skill\nupdated in registry")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=original_copied_at,
        copied_hash=baseline_hash,
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert — copied_at unchanged; only copied_hash updated
    assert result.exit_code == 0
    updated_config = read_project_config(tmp_path)
    assert updated_config.skills["alice/my-skill"].copied_at == original_copied_at
    assert updated_config.skills["alice/my-skill"].copied_hash != baseline_hash


@pytest.mark.anyio
async def test_update__registry_skill_dir_missing__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — skill tracked in .taken.yaml but registry dir deleted (drift)
    write_config(sample_config)
    write_registry(Registry(), taken_home)
    skill_dir = scaffold_project_skill("my-skill")

    pc = ProjectConfig()
    pc.skills["alice/my-skill"] = ProjectSkillEntry(
        copied_at=datetime.now(),
        copied_hash=compute_skill_hash(skill_dir),
    )
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)
    # Note: no scaffold_registry_skill call — registry dir intentionally absent

    # Act
    result = cli_runner.invoke(app, ["update", "alice/my-skill"])

    # Assert
    assert result.exit_code == 1
    assert "Registry Skill Missing" in result.output


# ---------------------------------------------------------------------------
# GitHub refresh pre-pass (source: taken, pin: floating)
# ---------------------------------------------------------------------------

_FAKE_SHA_OLD = "oldsha0" * 5 + "oldsha01"
_FAKE_SHA_NEW = "newsha0" * 5 + "newsha01"
_OLD_FOLDER_HASH = "oldfolderhash"
_NEW_FOLDER_HASH = "newfolderhash"


def _default_branch_main(owner: str, repo: str) -> str:  # noqa: ARG001
    return "main"


def _new_commit_sha(owner: str, repo: str, ref: str) -> str:  # noqa: ARG001
    return _FAKE_SHA_NEW


def _one_skill_changed(owner: str, repo: str, sha: str) -> list[GitHubSkill]:  # noqa: ARG001
    return [GitHubSkill(name="my-skill", skill_path="skills/my-skill", skill_folder_hash=_NEW_FOLDER_HASH)]


def _one_skill_unchanged(owner: str, repo: str, sha: str) -> list[GitHubSkill]:  # noqa: ARG001
    return [GitHubSkill(name="my-skill", skill_path="skills/my-skill", skill_folder_hash=_OLD_FOLDER_HASH)]


def _default_branch_raises(owner: str, repo: str) -> str:  # noqa: ARG001
    raise RuntimeError("network error")


def _default_branch_not_called(owner: str, repo: str) -> str:  # noqa: ARG001
    raise AssertionError("get_default_branch should not have been called")


def _download_creates_skill_md(
    owner: str,  # noqa: ARG001
    repo: str,  # noqa: ARG001
    skill_path: str,  # noqa: ARG001
    ref: str,  # noqa: ARG001
    dest: Path,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "SKILL.md").write_text("# my-skill\nrefreshed from github")


@pytest.mark.anyio
async def test_update__taken_source_floating__refreshed_from_github_when_changed(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — taken/floating skill with a different upstream folder hash
    write_config(sample_config)
    entry = RegistryEntryFactory.build(
        namespace="vercel-labs",
        name="my-skill",
        source=SkillSource.TAKEN,
        pin=VersionPin.FLOATING,
        repo="vercel-labs/agent-skills",
        version=_FAKE_SHA_OLD,
        skill_folder_hash=_OLD_FOLDER_HASH,
    )
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)

    registry_dir = scaffold_registry_skill("vercel-labs", "my-skill")
    project_dir = scaffold_project_skill("my-skill")
    (project_dir / "SKILL.md").write_text((registry_dir / "SKILL.md").read_text())
    baseline_hash = compute_skill_hash(project_dir)

    pc = ProjectConfig()
    pc.skills["vercel-labs/my-skill"] = ProjectSkillEntry(copied_at=datetime.now(), copied_hash=baseline_hash)
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("taken.commands.update.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.update.get_commit_sha", _new_commit_sha)
    monkeypatch.setattr("taken.commands.update.discover_skills", _one_skill_changed)
    monkeypatch.setattr("taken.commands.update.download_skill", _download_creates_skill_md)

    # Act
    result = cli_runner.invoke(app, ["update", "vercel-labs/my-skill"])

    # Assert — GitHub refresh happened
    assert result.exit_code == 0
    assert "Refreshed from GitHub" in result.output

    # Registry updated with new SHA and folder hash
    updated_registry = read_registry(taken_home)
    updated_entry = updated_registry.get("vercel-labs/my-skill")
    assert updated_entry is not None
    assert updated_entry.version == _FAKE_SHA_NEW
    assert updated_entry.skill_folder_hash == _NEW_FOLDER_HASH
    assert updated_entry.updated_at is not None

    # Project also updated (registry changed → local copy updated)
    assert (project_dir / "SKILL.md").read_text() == "# my-skill\nrefreshed from github"


@pytest.mark.anyio
async def test_update__taken_source_floating__up_to_date_when_hash_matches(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — same folder hash upstream: no refresh needed
    write_config(sample_config)
    entry = RegistryEntryFactory.build(
        namespace="vercel-labs",
        name="my-skill",
        source=SkillSource.TAKEN,
        pin=VersionPin.FLOATING,
        repo="vercel-labs/agent-skills",
        version=_FAKE_SHA_OLD,
        skill_folder_hash=_OLD_FOLDER_HASH,
    )
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)

    registry_dir = scaffold_registry_skill("vercel-labs", "my-skill")
    project_dir = scaffold_project_skill("my-skill")
    (project_dir / "SKILL.md").write_text((registry_dir / "SKILL.md").read_text())
    baseline_hash = compute_skill_hash(project_dir)

    pc = ProjectConfig()
    pc.skills["vercel-labs/my-skill"] = ProjectSkillEntry(copied_at=datetime.now(), copied_hash=baseline_hash)
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("taken.commands.update.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.update.get_commit_sha", _new_commit_sha)
    monkeypatch.setattr("taken.commands.update.discover_skills", _one_skill_unchanged)

    # Act
    result = cli_runner.invoke(app, ["update", "vercel-labs/my-skill"])

    # Assert — no refresh, no registry write
    assert result.exit_code == 0
    assert "Refreshed from GitHub" not in result.output
    assert "Already up to date" in result.output

    # Registry unchanged
    final_registry = read_registry(taken_home)
    assert final_registry.get("vercel-labs/my-skill") is not None
    assert final_registry.skills["vercel-labs/my-skill"].version == _FAKE_SHA_OLD


@pytest.mark.anyio
async def test_update__taken_source_pinned__skips_github_check(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — pinned skill: must not call get_default_branch
    write_config(sample_config)
    entry = RegistryEntryFactory.build(
        namespace="vercel-labs",
        name="my-skill",
        source=SkillSource.TAKEN,
        pin=VersionPin.PINNED,
        repo="vercel-labs/agent-skills",
        version=_FAKE_SHA_OLD,
        skill_folder_hash=_OLD_FOLDER_HASH,
    )
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)

    registry_dir = scaffold_registry_skill("vercel-labs", "my-skill")
    project_dir = scaffold_project_skill("my-skill")
    (project_dir / "SKILL.md").write_text((registry_dir / "SKILL.md").read_text())
    baseline_hash = compute_skill_hash(project_dir)

    pc = ProjectConfig()
    pc.skills["vercel-labs/my-skill"] = ProjectSkillEntry(copied_at=datetime.now(), copied_hash=baseline_hash)
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # If get_default_branch is called, it raises — test fails
    monkeypatch.setattr("taken.commands.update.get_default_branch", _default_branch_not_called)

    # Act
    result = cli_runner.invoke(app, ["update", "vercel-labs/my-skill"])

    # Assert — no AssertionError, normal local behavior
    assert result.exit_code == 0
    assert "Refreshed from GitHub" not in result.output


@pytest.mark.anyio
async def test_update__taken_source_floating__uses_local_when_github_fails(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — GitHub call fails; update should still work locally
    write_config(sample_config)
    entry = RegistryEntryFactory.build(
        namespace="vercel-labs",
        name="my-skill",
        source=SkillSource.TAKEN,
        pin=VersionPin.FLOATING,
        repo="vercel-labs/agent-skills",
        version=_FAKE_SHA_OLD,
        skill_folder_hash=_OLD_FOLDER_HASH,
    )
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)

    registry_dir = scaffold_registry_skill("vercel-labs", "my-skill")
    project_dir = scaffold_project_skill("my-skill")
    (project_dir / "SKILL.md").write_text((registry_dir / "SKILL.md").read_text())
    baseline_hash = compute_skill_hash(project_dir)

    pc = ProjectConfig()
    pc.skills["vercel-labs/my-skill"] = ProjectSkillEntry(copied_at=datetime.now(), copied_hash=baseline_hash)
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("taken.commands.update.get_default_branch", _default_branch_raises)

    # Act
    result = cli_runner.invoke(app, ["update", "vercel-labs/my-skill"])

    # Assert — warning printed, local copy still up to date
    assert result.exit_code == 0
    assert "Could not reach GitHub" in result.output
    assert "Refreshed from GitHub" not in result.output


@pytest.mark.anyio
async def test_update__taken_source_no_skill_folder_hash__skips_github(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scaffold_registry_skill: Callable[[str, str], Path],
    scaffold_project_skill: Callable[[str], Path],
) -> None:
    # Arrange — taken/floating but no skill_folder_hash baseline: skip GitHub check
    write_config(sample_config)
    entry = RegistryEntryFactory.build(
        namespace="vercel-labs",
        name="my-skill",
        source=SkillSource.TAKEN,
        pin=VersionPin.FLOATING,
        repo="vercel-labs/agent-skills",
        version=_FAKE_SHA_OLD,
        skill_folder_hash=None,
    )
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)

    registry_dir = scaffold_registry_skill("vercel-labs", "my-skill")
    project_dir = scaffold_project_skill("my-skill")
    (project_dir / "SKILL.md").write_text((registry_dir / "SKILL.md").read_text())
    baseline_hash = compute_skill_hash(project_dir)

    pc = ProjectConfig()
    pc.skills["vercel-labs/my-skill"] = ProjectSkillEntry(copied_at=datetime.now(), copied_hash=baseline_hash)
    write_project_config(pc, tmp_path)
    monkeypatch.chdir(tmp_path)

    # get_default_branch must NOT be called
    monkeypatch.setattr("taken.commands.update.get_default_branch", _default_branch_not_called)

    # Act
    result = cli_runner.invoke(app, ["update", "vercel-labs/my-skill"])

    # Assert — no AssertionError, proceeds with local-only check
    assert result.exit_code == 0
    assert "Refreshed from GitHub" not in result.output
