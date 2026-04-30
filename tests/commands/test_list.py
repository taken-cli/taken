from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taken.core.config import write_config
from taken.core.registry import write_registry
from taken.main import app
from taken.models.config import TakenConfig
from taken.models.registry import Registry, SkillSource
from tests.fixtures.registry import RegistryEntryFactory


@pytest.mark.anyio
async def test_list__not_initialized__exits_with_error(
    cli_runner: CliRunner,
) -> None:
    # Arrange — config absent (taken_home is empty)

    # Act
    result = cli_runner.invoke(app, ["list"])

    # Assert
    assert result.exit_code == 1
    assert "Not Initialized" in result.output


@pytest.mark.anyio
async def test_list__empty_registry__shows_empty_message(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)
    write_registry(Registry(), taken_home)

    # Act
    result = cli_runner.invoke(app, ["list"])

    # Assert
    assert result.exit_code == 0
    assert "No skills registered yet" in result.output
    assert "taken add" in result.output


@pytest.mark.anyio
async def test_list__single_personal_skill__shows_skill_with_columns_and_count(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange
    write_config(sample_config)
    entry = RegistryEntryFactory.build(
        namespace="alice",
        name="my-skill",
        source=SkillSource.PERSONAL,
        version="1",
        created_at=datetime(2025, 1, 15),
        installed_at=None,
    )
    registry = Registry()
    registry.add(entry)
    write_registry(registry, taken_home)

    # Act
    result = cli_runner.invoke(app, ["list"])

    # Assert
    assert result.exit_code == 0
    assert "alice/my-skill" in result.output
    assert "personal" in result.output
    assert "2025-01-15" in result.output
    assert "1 skill" in result.output  # singular
    assert "Skill" in result.output
    assert "Source" in result.output
    assert "Version" in result.output
    assert "Date" in result.output


@pytest.mark.anyio
async def test_list__multiple_skills__sorted_with_correct_formatting(
    taken_home: Path,
    cli_runner: CliRunner,
    sample_config: TakenConfig,
) -> None:
    # Arrange — entries covering sorted order, plural count, version truncation, and em-dash for None
    write_config(sample_config)
    e1 = RegistryEntryFactory.build(
        namespace="bob",
        name="z-skill",
        source=SkillSource.NPX,
        version="abc123456789",  # > 8 chars — should be truncated to "abc12345"
        installed_at=datetime(2025, 3, 1),
        created_at=None,
    )
    e2 = RegistryEntryFactory.build(
        namespace="alice",
        name="a-skill",
        source=SkillSource.PERSONAL,
        version="1",
        created_at=datetime(2025, 1, 1),
        installed_at=None,
    )
    e3 = RegistryEntryFactory.build(
        namespace="alice",
        name="m-skill",
        source=SkillSource.TAKEN,
        version=None,  # exercises "—" version display
        created_at=None,
        installed_at=None,  # exercises "—" date display
    )
    registry = Registry()
    for e in [e1, e2, e3]:
        registry.add(e)
    write_registry(registry, taken_home)

    # Act
    result = cli_runner.invoke(app, ["list"])

    # Assert
    assert result.exit_code == 0
    assert "alice/a-skill" in result.output
    assert "alice/m-skill" in result.output
    assert "bob/z-skill" in result.output
    assert "3 skills" in result.output  # plural
    assert "abc12345" in result.output  # truncated to 8 chars
    assert "abc123456789" not in result.output  # full version absent
    assert "—" in result.output  # em-dash for None version/date
    assert "personal" in result.output
    assert "npx" in result.output
    assert "taken" in result.output
    # Verify sort order by position in output
    idx_a = result.output.index("alice/a-skill")
    idx_m = result.output.index("alice/m-skill")
    idx_z = result.output.index("bob/z-skill")
    assert idx_a < idx_m < idx_z
