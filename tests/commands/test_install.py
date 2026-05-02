from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.github import GitHubSkill
from taken.core.registry import read_registry
from taken.main import app
from taken.models.config import TakenConfig
from taken.models.registry import VersionPin

_FAKE_SHA = "abc123def456abc123def456abc123def456abc1"
_FAKE_SKILL_HASH = "deadbeefdeadbeef"


# ---------------------------------------------------------------------------
# Typed mock helpers
# ---------------------------------------------------------------------------


def _default_branch_main(owner: str, repo: str) -> str:  # noqa: ARG001
    return "main"


def _commit_sha_fixed(owner: str, repo: str, ref: str) -> str:  # noqa: ARG001
    return _FAKE_SHA


def _one_skill(owner: str, repo: str, sha: str) -> list[GitHubSkill]:  # noqa: ARG001
    return [GitHubSkill(name="my-skill", skill_path="skills/my-skill", skill_folder_hash=_FAKE_SKILL_HASH)]


def _two_skills(owner: str, repo: str, sha: str) -> list[GitHubSkill]:  # noqa: ARG001
    return [
        GitHubSkill(name="skill-a", skill_path="skills/skill-a", skill_folder_hash="hash-a"),
        GitHubSkill(name="skill-b", skill_path="skills/skill-b", skill_folder_hash="hash-b"),
    ]


def _no_skills(owner: str, repo: str, sha: str) -> list[GitHubSkill]:  # noqa: ARG001
    return []


def _raise_file_not_found(owner: str, repo: str, sha: str) -> list[GitHubSkill]:  # noqa: ARG001
    raise FileNotFoundError("repo not found")


def _raise_permission_error(owner: str, repo: str, sha: str) -> list[GitHubSkill]:  # noqa: ARG001
    raise PermissionError("rate limited")


def _download_creates_skill_md(
    owner: str,  # noqa: ARG001
    repo: str,  # noqa: ARG001
    skill_path: str,  # noqa: ARG001
    ref: str,  # noqa: ARG001
    dest: Path,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "SKILL.md").write_text(f"---\nname: {dest.name}\ndescription: test\n---\n")


def _get_default_branch_not_called(owner: str, repo: str) -> str:  # noqa: ARG001
    raise AssertionError("get_default_branch should not have been called")


# ---------------------------------------------------------------------------
# Guard tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_install__not_initialized__exits_with_error(
    cli_runner: CliRunner,
) -> None:
    # Arrange — no config written

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills"])

    # Assert
    assert result.exit_code == 1
    assert "Not Initialized" in result.output


@pytest.mark.anyio
async def test_install__invalid_format__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)

    # Act — source with no slash at all
    result = cli_runner.invoke(app, ["install", "nodotslash"])

    # Assert
    assert result.exit_code == 1
    assert "Invalid Source" in result.output


# ---------------------------------------------------------------------------
# Source parsing
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_install__npx_prefix__parsed_and_installed(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _one_skill)
    monkeypatch.setattr("taken.commands.install.download_skill", _download_creates_skill_md)

    # Act
    result = cli_runner.invoke(app, ["install", "npx skills add vercel-labs/agent-skills"])

    # Assert
    assert result.exit_code == 0
    assert "Skills Installed" in result.output
    assert (taken_home / "skills" / "vercel-labs" / "my-skill" / "SKILL.md").exists()


@pytest.mark.anyio
async def test_install__github_url__parsed_and_installed(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _one_skill)
    monkeypatch.setattr("taken.commands.install.download_skill", _download_creates_skill_md)

    # Act
    result = cli_runner.invoke(app, ["install", "https://github.com/vercel-labs/agent-skills"])

    # Assert
    assert result.exit_code == 0
    assert "Skills Installed" in result.output
    assert (taken_home / "skills" / "vercel-labs" / "my-skill" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# GitHub error paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_install__repo_not_found__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _raise_file_not_found)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills"])

    # Assert
    assert result.exit_code == 1
    assert "Not Found" in result.output


@pytest.mark.anyio
async def test_install__rate_limit__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _raise_permission_error)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills"])

    # Assert
    assert result.exit_code == 1
    assert "GitHub API Error" in result.output


@pytest.mark.anyio
async def test_install__no_skills_in_repo__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _no_skills)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills"])

    # Assert
    assert result.exit_code == 1
    assert "No Skills Found" in result.output


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_install__single_skill__installed_and_registered(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _one_skill)
    monkeypatch.setattr("taken.commands.install.download_skill", _download_creates_skill_md)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills"])

    # Assert output
    assert result.exit_code == 0
    assert "Skills Installed" in result.output
    assert "vercel-labs/my-skill" in result.output
    assert _FAKE_SHA[:8] in result.output

    # Assert files on disk
    skill_dir = taken_home / "skills" / "vercel-labs" / "my-skill"
    assert skill_dir.is_dir()
    assert (skill_dir / "SKILL.md").exists()

    # Assert registry entry — all key fields
    registry = read_registry(taken_home)
    entry = registry.get("vercel-labs/my-skill")
    assert entry is not None
    assert entry.source.value == "taken"
    assert entry.version == _FAKE_SHA
    assert entry.repo == "vercel-labs/agent-skills"
    assert entry.source_url == "https://github.com/vercel-labs/agent-skills"
    assert entry.skill_path == "skills/my-skill"
    assert entry.skill_folder_hash == _FAKE_SKILL_HASH
    assert entry.installed_at is not None
    assert entry.pin.value == "floating"


# ---------------------------------------------------------------------------
# Skill filter
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_install__skill_flag__installs_only_named_skill(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — repo has two skills; user selects only skill-b via --skill flag
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _two_skills)
    monkeypatch.setattr("taken.commands.install.download_skill", _download_creates_skill_md)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills", "--skill", "skill-b"])

    # Assert
    assert result.exit_code == 0
    assert "vercel-labs/skill-b" in result.output
    assert (taken_home / "skills" / "vercel-labs" / "skill-b" / "SKILL.md").exists()
    assert not (taken_home / "skills" / "vercel-labs" / "skill-a").exists()


@pytest.mark.anyio
async def test_install__path_filter__installs_only_named_skill(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — skill name embedded in path: owner/repo/skill-name
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _two_skills)
    monkeypatch.setattr("taken.commands.install.download_skill", _download_creates_skill_md)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills/skill-a"])

    # Assert
    assert result.exit_code == 0
    assert "vercel-labs/skill-a" in result.output
    assert (taken_home / "skills" / "vercel-labs" / "skill-a" / "SKILL.md").exists()
    assert not (taken_home / "skills" / "vercel-labs" / "skill-b").exists()


@pytest.mark.anyio
async def test_install__skill_filter_no_match__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _two_skills)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills", "--skill", "bad-name"])

    # Assert
    assert result.exit_code == 1
    assert "Skill Not Found" in result.output
    assert "skill-a" in result.output  # available names listed


# ---------------------------------------------------------------------------
# Duplicate / skip
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_install__already_in_registry__skipped(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — pre-create the dest dir so it looks already installed
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _one_skill)

    existing = taken_home / "skills" / "vercel-labs" / "my-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("# existing")

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills"])

    # Assert — exits 0 with skipped note; no write to registry
    assert result.exit_code == 0
    assert "skipped" in result.output.lower()
    assert "Skills Installed" not in result.output


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_install__with_pin_flag__registry_entry_pinned(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _one_skill)
    monkeypatch.setattr("taken.commands.install.download_skill", _download_creates_skill_md)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills", "--pin"])

    # Assert
    assert result.exit_code == 0
    registry = read_registry(taken_home)
    entry = registry.get("vercel-labs/my-skill")
    assert entry is not None
    assert entry.pin == VersionPin.PINNED


@pytest.mark.anyio
async def test_install__with_ref_flag__skips_default_branch_call(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — get_default_branch must NOT be called when --ref is passed
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _get_default_branch_not_called)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _one_skill)
    monkeypatch.setattr("taken.commands.install.download_skill", _download_creates_skill_md)

    # Act
    result = cli_runner.invoke(app, ["install", "vercel-labs/agent-skills", "--ref", "main"])

    # Assert — no AssertionError from the mock, install succeeded
    assert result.exit_code == 0
    assert "Skills Installed" in result.output


# ---------------------------------------------------------------------------
# Multiple skills
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_install__multiple_skills__all_installed(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — two skills; pass both via --skill to avoid interactive picker
    write_config(sample_config)
    monkeypatch.setattr("taken.commands.install.get_default_branch", _default_branch_main)
    monkeypatch.setattr("taken.commands.install.get_commit_sha", _commit_sha_fixed)
    monkeypatch.setattr("taken.commands.install.discover_skills", _two_skills)
    monkeypatch.setattr("taken.commands.install.download_skill", _download_creates_skill_md)

    # Act — select both by using --skill twice
    result = cli_runner.invoke(
        app,
        ["install", "vercel-labs/agent-skills", "--skill", "skill-a", "--skill", "skill-b"],
    )

    # Assert
    assert result.exit_code == 0
    assert "vercel-labs/skill-a" in result.output
    assert "vercel-labs/skill-b" in result.output
    assert (taken_home / "skills" / "vercel-labs" / "skill-a" / "SKILL.md").exists()
    assert (taken_home / "skills" / "vercel-labs" / "skill-b" / "SKILL.md").exists()

    registry = read_registry(taken_home)
    assert registry.exists("vercel-labs/skill-a")
    assert registry.exists("vercel-labs/skill-b")
