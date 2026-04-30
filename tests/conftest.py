from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.models.config import TakenConfig
from taken.models.registry import RegistryEntry
from tests.fixtures.config import TakenConfigFactory
from tests.fixtures.registry import RegistryEntryFactory


@pytest.fixture
def taken_home(tmp_path: Path) -> Path:
    home = tmp_path / ".taken"
    home.mkdir()
    return home


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def sample_config(taken_home: Path) -> TakenConfig:
    return TakenConfigFactory.build(taken_home=taken_home)


@pytest.fixture
def sample_registry_entry() -> RegistryEntry:
    return RegistryEntryFactory.build()
