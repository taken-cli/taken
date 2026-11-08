import getpass
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.mark.integration
def test_init_add_use_save_update__full_local_workflow__state_consistent(
    taken_home: Path,
    run: Callable[..., subprocess.CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    # Arrange
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    username = getpass.getuser()

    # Act — init
    result = run(["taken", "init"], input="1\n")
    assert result.returncode == 0, result.stderr
    assert (taken_home / "config.yaml").exists()
    assert (taken_home / "registry.yaml").exists()

    # Act — add
    result = run(["taken", "add", "my-skill"])
    assert result.returncode == 0, result.stderr
    assert (taken_home / "skills" / username / "my-skill" / "SKILL.md").exists()

    # Act — use
    result = run(["taken", "use", f"{username}/my-skill"], cwd=project_dir)
    assert result.returncode == 0, result.stderr
    assert (project_dir / ".agents" / "skills" / "my-skill").is_dir()
    assert (project_dir / ".taken.yaml").exists()

    # Arrange — edit the project copy
    skill_file = project_dir / ".agents" / "skills" / "my-skill" / "SKILL.md"
    skill_file.write_text("# Edited skill\n")

    # Act — save
    result = run(["taken", "save", f"{username}/my-skill"], cwd=project_dir)
    assert result.returncode == 0, result.stderr
    assert (taken_home / "skills" / username / "my-skill" / "SKILL.md").read_text() == "# Edited skill\n"

    # Act — update (project is now in sync — should report up to date)
    result = run(["taken", "update", f"{username}/my-skill"], cwd=project_dir)
    assert result.returncode == 0, result.stderr


@pytest.mark.integration
def test_list_and_remove__after_add__registry_empty(
    taken_home: Path,
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    # Arrange
    username = getpass.getuser()
    run(["taken", "init"], input="1\n")
    run(["taken", "add", "to-remove"])

    # Act — list
    result = run(["taken", "list"])
    assert result.returncode == 0, result.stderr
    assert f"{username}/to-remove" in result.stdout

    # Act — remove
    result = run(["taken", "remove", f"{username}/to-remove"], input="y\n")
    assert result.returncode == 0, result.stderr
    assert not (taken_home / "skills" / username / "to-remove").exists()

    # Assert — list now empty
    result = run(["taken", "list"])
    assert result.returncode == 0
    assert f"{username}/to-remove" not in result.stdout


@pytest.mark.integration
def test_commands__not_initialized__exit_nonzero(
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    # Arrange — taken_home exists but init never run

    # Act / Assert
    for cmd in [
        ["taken", "add", "my-skill"],
        ["taken", "list"],
        ["taken", "remove", "x/y"],
    ]:
        result = run(cmd)
        assert result.returncode != 0, f"{cmd} should fail when not initialized"
