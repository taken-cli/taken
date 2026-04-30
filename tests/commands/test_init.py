import getpass
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import read_config, write_config
from taken.core.registry import read_registry, write_registry
from taken.main import app
from taken.models.config import TakenConfig
from taken.models.registry import Registry, RegistryEntry
from tests.fixtures.registry import RegistryEntryFactory

pytestmark = pytest.mark.anyio


async def test_init_fresh_creates_config_and_registry(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange — taken_home patched via autouse fixture in conftest

    # Act
    result = cli_runner.invoke(app, ["init"], input="1\n")

    # Assert
    assert result.exit_code == 0
    assert (taken_home / "config.yaml").exists()
    assert (taken_home / "registry.yaml").exists()


async def test_init_config_roundtrip(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange — taken_home patched via autouse fixture in conftest

    # Act
    result = cli_runner.invoke(app, ["init"], input="1\n")

    # Assert
    assert result.exit_code == 0
    config = read_config(taken_home)
    assert config.username == getpass.getuser()
    assert config.taken_home == taken_home


async def test_init_registry_is_empty_on_fresh_init(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange — taken_home patched via autouse fixture in conftest

    # Act
    cli_runner.invoke(app, ["init"], input="1\n")

    # Assert
    registry = read_registry(taken_home)
    assert registry.skills == {}


async def test_init_creates_skills_directory(
    taken_home: Path,
    cli_runner: CliRunner,
) -> None:
    # Arrange — taken_home patched via autouse fixture in conftest

    # Act
    cli_runner.invoke(app, ["init"], input="1\n")

    # Assert
    username = getpass.getuser()
    assert (taken_home / "skills" / username).is_dir()


async def test_init_already_initialized_abort(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)
    original_username = sample_config.username

    # Act — user declines reinitialize prompt
    result = cli_runner.invoke(app, ["init"], input="n\n")

    # Assert
    assert result.exit_code == 0
    config = read_config(taken_home)
    assert config.username == original_username


async def test_init_already_initialized_reset_config_only(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    sample_registry_entry: RegistryEntry,
) -> None:
    # Arrange
    write_config(sample_config)
    registry = Registry()
    registry.add(sample_registry_entry)
    write_registry(registry, taken_home)

    # Act — reinit → reset config only → pick system username
    result = cli_runner.invoke(app, ["init"], input="y\n1\n1\n")

    # Assert
    assert result.exit_code == 0
    updated_registry = read_registry(taken_home)
    assert sample_registry_entry.full_name in updated_registry.skills


async def test_init_already_initialized_full_wipe(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
    sample_registry_entry: RegistryEntry,
) -> None:
    # Arrange
    write_config(sample_config)
    registry = Registry()
    registry.add(sample_registry_entry)
    write_registry(registry, taken_home)
    (taken_home / "skills").mkdir(parents=True, exist_ok=True)

    # Act — reinit → full wipe → confirm → pick system username
    result = cli_runner.invoke(app, ["init"], input="y\n2\ny\n1\n")

    # Assert
    assert result.exit_code == 0
    updated_registry = read_registry(taken_home)
    assert updated_registry.skills == {}


async def test_init_already_initialized_full_wipe_abort_confirm(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)
    original_username = sample_config.username

    # Act — reinit → full wipe → abort on second confirm
    result = cli_runner.invoke(app, ["init"], input="y\n2\nn\n")

    # Assert
    assert result.exit_code == 0
    config = read_config(taken_home)
    assert config.username == original_username


async def test_init_preserves_registry_when_exists_on_config_reset(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)
    entry1 = RegistryEntryFactory.build()
    entry2 = RegistryEntryFactory.build()
    registry = Registry()
    registry.add(entry1)
    registry.add(entry2)
    write_registry(registry, taken_home)

    # Act — reinit → reset config only → pick system username
    result = cli_runner.invoke(app, ["init"], input="y\n1\n1\n")

    # Assert
    assert result.exit_code == 0
    updated_registry = read_registry(taken_home)
    assert entry1.full_name in updated_registry.skills
    assert entry2.full_name in updated_registry.skills


async def test_init_username_manual_entry(
    taken_home: Path,
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — force no git name so choices are ["1", "2"] (manual as option 2)
    monkeypatch.setattr("getpass.getuser", lambda: "testuser")
    mock_result: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(args=[], returncode=0, stdout="")

    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return mock_result

    monkeypatch.setattr("subprocess.run", _no_git)

    # Act — "2" → manual entry, then type "myname"
    result = cli_runner.invoke(app, ["init"], input="2\nmyname\n")

    # Assert
    assert result.exit_code == 0
    config = read_config(taken_home)
    assert config.username == "myname"
