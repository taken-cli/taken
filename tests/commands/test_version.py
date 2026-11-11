from importlib.metadata import version

import pytest
from typer.testing import CliRunner

from taken.main import app


@pytest.mark.anyio
@pytest.mark.parametrize("flag", ["--version", "-V"])
async def test_version__flag__prints_installed_version(cli_runner: CliRunner, flag: str) -> None:
    # Arrange
    expected = version("taken-cli")

    # Act
    result = cli_runner.invoke(app, [flag])

    # Assert
    assert result.exit_code == 0
    assert result.output.strip() == f"taken {expected}"


@pytest.mark.anyio
async def test_version__no_args__still_shows_help(cli_runner: CliRunner) -> None:
    # Arrange — nothing to set up

    # Act
    result = cli_runner.invoke(app, [])

    # Assert
    assert "Usage" in result.output
    assert "init" in result.output
