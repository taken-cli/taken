from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import read_config, write_config
from taken.main import app
from taken.models.config import TakenConfig


def _no_git(*_args: object, **_kwargs: object) -> None:
    return None


@pytest.fixture(autouse=True)
def skip_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taken.commands.mirrors.auto_commit_and_push", _no_git)


@pytest.mark.anyio
async def test_mirrors__not_initialized__exits_with_error(cli_runner: CliRunner) -> None:
    # Arrange — no config written

    # Act
    result = cli_runner.invoke(app, ["mirrors", "list"])

    # Assert
    assert result.exit_code == 1
    assert "Not Initialized" in result.output


@pytest.mark.anyio
async def test_mirrors__list__shows_main_dir_mode_and_mirrors(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)

    # Act
    result = cli_runner.invoke(app, ["mirrors", "list"])

    # Assert
    assert result.exit_code == 0
    assert ".agents/skills" in result.output
    assert "symlink" in result.output
    assert ".claude/skills" in result.output


@pytest.mark.anyio
async def test_mirrors__add_with_trailing_slash__normalized_and_saved(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)

    # Act
    result = cli_runner.invoke(app, ["mirrors", "add", ".cursor/skills/"])

    # Assert
    assert result.exit_code == 0
    assert read_config(taken_home).skills.mirror_dirs == [".claude/skills", ".cursor/skills"]


@pytest.mark.anyio
async def test_mirrors__add_duplicate__no_change(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)

    # Act
    result = cli_runner.invoke(app, ["mirrors", "add", ".claude/skills"])

    # Assert
    assert result.exit_code == 0
    assert "already" in result.output
    assert read_config(taken_home).skills.mirror_dirs == [".claude/skills"]


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ["/abs/skills", "~/skills", "../outside", ".agents/skills"])
async def test_mirrors__add_invalid_dir__exits_with_error(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    bad: str,
) -> None:
    # Arrange
    write_config(sample_config)

    # Act
    result = cli_runner.invoke(app, ["mirrors", "add", bad])

    # Assert
    assert result.exit_code == 1
    assert "Invalid Mirror Dir" in result.output
    assert read_config(taken_home).skills.mirror_dirs == [".claude/skills"]


@pytest.mark.anyio
async def test_mirrors__remove_existing__removed_from_config(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)

    # Act
    result = cli_runner.invoke(app, ["mirrors", "remove", ".claude/skills"])

    # Assert
    assert result.exit_code == 0
    assert read_config(taken_home).skills.mirror_dirs == []


@pytest.mark.anyio
async def test_mirrors__remove_unknown__exits_with_error(
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)

    # Act
    result = cli_runner.invoke(app, ["mirrors", "remove", ".cursor/skills"])

    # Assert
    assert result.exit_code == 1
    assert "Not Found" in result.output
