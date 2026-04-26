import shutil
from datetime import datetime
from pathlib import Path

import typer
from InquirerPy import inquirer
from InquirerPy.enum import (
    INQUIRERPY_EMPTY_CIRCLE_SEQUENCE,
    INQUIRERPY_FILL_CIRCLE_SEQUENCE,
)
from rich.panel import Panel

from taken.core.config import is_config_exists
from taken.core.project import read_project_config, write_project_config
from taken.core.registry import read_registry
from taken.models.project import ProjectSkillEntry
from taken.utils.console import console, err_console

TAKEN_HOME = Path.home() / ".taken"


def use(
    namespace_skill: str | None = typer.Argument(
        None,
        help="Skill to copy into project, e.g. pradyothsp/hello-world. Omit for interactive picker.",
    ),
) -> None:
    """Copy skill(s) from ~/.taken/ into the current project's .agents/ directory."""
    if not is_config_exists(TAKEN_HOME):
        err_console.print(
            Panel(
                "Taken is not initialized. Run [bold]taken init[/bold] to get started.",
                title="[red]Not Initialized[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    registry = read_registry(TAKEN_HOME)

    if not registry.skills:
        err_console.print(
            Panel(
                "No skills in your registry yet. Run [bold]taken add[/bold] to create one.",
                title="[red]Registry Empty[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    if namespace_skill is not None:
        entry = registry.get(namespace_skill)
        if entry is None:
            err_console.print(
                Panel(
                    f"[bold]{namespace_skill}[/bold] not found in registry.\n"
                    "Run [bold]taken list[/bold] to see available skills.",
                    title="[red]Skill Not Found[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)
        selected = [entry]
    else:
        choices = [
            {"name": f"{e.full_name}  [{e.source.value}]", "value": e.full_name}
            for e in sorted(registry.skills.values(), key=lambda e: e.full_name)
        ]
        selected_names: list[str] = inquirer.fuzzy(  # type: ignore[attr-defined]
            message="Search skills:",
            choices=choices,
            multiselect=True,
            marker=INQUIRERPY_FILL_CIRCLE_SEQUENCE,
            marker_pl=INQUIRERPY_EMPTY_CIRCLE_SEQUENCE,
            instruction="(type to filter  space/tab to select  enter to confirm)",
            keybindings={"toggle": [{"key": "space"}, {"key": "tab"}]},
            validate=lambda x: len(x) > 0,
            invalid_message="Select at least one skill.",
        ).execute()

        if not selected_names:
            raise typer.Exit(code=0)

        selected = [
            e for name in selected_names if (e := registry.get(name)) is not None
        ]

    project_config = read_project_config(Path.cwd())
    agents_dir = Path.cwd() / project_config.skills_dir
    agents_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    copied: list[str] = []

    for entry in selected:
        src = TAKEN_HOME / "skills" / entry.namespace / entry.name
        dst = agents_dir / entry.name

        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

        project_config.skills[entry.full_name] = ProjectSkillEntry(
            copied_at=now,
            registry_version=entry.version,
        )
        copied.append(
            f"[green]✓[/green] [bold]{entry.full_name}[/bold] → {project_config.skills_dir}/{entry.name}/"
        )

    write_project_config(project_config, Path.cwd())

    lines = "\n".join(copied) + "\n\n[dim]Tracked in .taken.yaml[/dim]"
    console.print(
        Panel(
            lines,
            title="[green]Skills Added[/green]",
            border_style="green",
            padding=(1, 2),
        )
    )
