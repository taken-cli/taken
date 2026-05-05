from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.git import auto_commit_and_push, is_git_repo
from taken.core.registry import write_registry
from taken.main import app
from taken.models.config import GitConfig
from taken.models.registry import Registry, RegistryEntry, SkillSource
from tests.fixtures.config import TakenConfigFactory


def _mock_run_ok() -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = ""
    m.stderr = ""
    return m


@pytest.mark.anyio
async def test_init__fresh_init__git_init_and_initial_commit_issued(
    cli_runner: CliRunner,
) -> None:
    # Arrange — taken_home patched via autouse fixture in conftest

    # Act
    with patch("taken.core.git._run", return_value=_mock_run_ok()) as mock_run:
        result = cli_runner.invoke(app, ["init"], input="1\n")

    # Assert
    assert result.exit_code == 0
    issued = [c.args[0] for c in mock_run.call_args_list]
    assert ["git", "init"] in issued
    assert any(args[:3] == ["git", "commit", "-m"] and "initialize taken home" in args[3] for args in issued)


@pytest.mark.anyio
async def test_init__reinit__reinit_commit_issued_without_git_init(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange — simulate existing repo by creating .git dir
    (taken_home / ".git").mkdir()
    config = TakenConfigFactory.build(taken_home=taken_home)
    write_config(config)
    write_registry(Registry(), taken_home)

    # Act
    with patch("taken.core.git._run", return_value=_mock_run_ok()) as mock_run:
        result = cli_runner.invoke(app, ["init"], input="y\n1\n1\n")

    # Assert
    assert result.exit_code == 0
    issued = [c.args[0] for c in mock_run.call_args_list]
    assert any(args[:3] == ["git", "commit", "-m"] and "reinitialize taken home" in args[3] for args in issued)
    assert ["git", "init"] not in issued


@pytest.mark.anyio
async def test_is_git_repo__git_dir_present__returns_true(taken_home: Path) -> None:
    # Arrange
    (taken_home / ".git").mkdir()

    # Act / Assert
    assert is_git_repo(taken_home) is True


@pytest.mark.anyio
async def test_is_git_repo__no_git_dir__returns_false(taken_home: Path) -> None:
    # Arrange — taken_home exists but has no .git

    # Act / Assert
    assert is_git_repo(taken_home) is False


@pytest.mark.anyio
async def test_add__auto_commit_enabled__commit_issued_with_correct_message(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange
    config = TakenConfigFactory.build(taken_home=taken_home, git=GitConfig(auto_commit=True, auto_push=False))
    write_config(config)
    write_registry(Registry(), taken_home)
    (taken_home / "skills" / config.username).mkdir(parents=True, exist_ok=True)
    (taken_home / ".git").mkdir()

    # Act
    with (
        patch("taken.core.git._run", return_value=_mock_run_ok()) as mock_run,
        patch("taken.core.git._has_changes", return_value=True),
    ):
        result = cli_runner.invoke(app, ["add", "my-skill"])

    # Assert
    assert result.exit_code == 0
    issued = [c.args[0] for c in mock_run.call_args_list]
    assert any(args[:3] == ["git", "commit", "-m"] and f"add: {config.username}/my-skill" in args[3] for args in issued)


@pytest.mark.anyio
async def test_add__auto_commit_disabled__no_commit_issued(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange
    config = TakenConfigFactory.build(taken_home=taken_home, git=GitConfig(auto_commit=False, auto_push=False))
    write_config(config)
    write_registry(Registry(), taken_home)
    (taken_home / "skills" / config.username).mkdir(parents=True, exist_ok=True)
    (taken_home / ".git").mkdir()

    # Act
    with patch("taken.core.git._run", return_value=_mock_run_ok()) as mock_run:
        result = cli_runner.invoke(app, ["add", "my-skill"])

    # Assert
    assert result.exit_code == 0
    issued = [c.args[0] for c in mock_run.call_args_list]
    assert not any(args[:2] == ["git", "commit"] for args in issued)


@pytest.mark.anyio
async def test_remove__auto_commit_enabled__commit_issued_with_correct_message(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange
    config = TakenConfigFactory.build(taken_home=taken_home, git=GitConfig(auto_commit=True, auto_push=False))
    write_config(config)
    entry = RegistryEntry(namespace=config.username, name="my-skill", source=SkillSource.PERSONAL)
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)
    (taken_home / ".git").mkdir()

    # Act
    with (
        patch("taken.core.git._run", return_value=_mock_run_ok()) as mock_run,
        patch("taken.core.git._has_changes", return_value=True),
    ):
        result = cli_runner.invoke(app, ["remove", f"{config.username}/my-skill"], input="y\n")

    # Assert
    assert result.exit_code == 0
    issued = [c.args[0] for c in mock_run.call_args_list]
    assert any(
        args[:3] == ["git", "commit", "-m"] and f"remove: {config.username}/my-skill" in args[3] for args in issued
    )


@pytest.mark.anyio
async def test_auto_commit_and_push__auto_push_enabled__push_issued(
    taken_home: Path,
) -> None:
    # Arrange
    config = TakenConfigFactory.build(taken_home=taken_home, git=GitConfig(auto_commit=True, auto_push=True))
    write_config(config)
    (taken_home / ".git").mkdir()

    # Act
    with (
        patch("taken.core.git._run", return_value=_mock_run_ok()) as mock_run,
        patch("taken.core.git._has_changes", return_value=True),
    ):
        auto_commit_and_push(taken_home, "test: message")

    # Assert
    issued = [c.args[0] for c in mock_run.call_args_list]
    assert ["git", "push"] in issued


@pytest.mark.anyio
async def test_auto_commit_and_push__push_fails__does_not_raise(
    taken_home: Path,
) -> None:
    # Arrange
    config = TakenConfigFactory.build(taken_home=taken_home, git=GitConfig(auto_commit=True, auto_push=True))
    write_config(config)
    (taken_home / ".git").mkdir()

    fail = MagicMock(returncode=1, stdout="", stderr="No remote configured")
    ok = _mock_run_ok()

    def _side_effect(args: list[str], _cwd: Path) -> MagicMock:
        return fail if args == ["git", "push"] else ok

    # Act — push fails; must not raise
    with (
        patch("taken.core.git._run", side_effect=_side_effect),
        patch("taken.core.git._has_changes", return_value=True),
    ):
        auto_commit_and_push(taken_home, "test: message")


@pytest.mark.anyio
async def test_auto_commit_and_push__nothing_to_commit__commit_not_issued(
    taken_home: Path,
) -> None:
    # Arrange
    config = TakenConfigFactory.build(taken_home=taken_home, git=GitConfig(auto_commit=True, auto_push=False))
    write_config(config)

    # Act
    with (
        patch("taken.core.git._run", return_value=_mock_run_ok()) as mock_run,
        patch("taken.core.git._has_changes", return_value=False),
    ):
        auto_commit_and_push(taken_home, "test: message")

    # Assert
    issued = [c.args[0] for c in mock_run.call_args_list]
    assert not any(args[:2] == ["git", "commit"] for args in issued)


@pytest.mark.anyio
async def test_git_passthrough__status_arg__runs_git_in_taken_home(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange
    config = TakenConfigFactory.build(taken_home=taken_home)
    write_config(config)

    # Act
    with patch("taken.core.git.subprocess.run", return_value=MagicMock(returncode=0)) as mock_sub:
        cli_runner.invoke(app, ["git", "status"])

    # Assert — git status called with taken_home as cwd
    assert mock_sub.called
    assert mock_sub.call_args.args[0] == ["git", "status"]
    assert mock_sub.call_args.kwargs["cwd"] == taken_home
