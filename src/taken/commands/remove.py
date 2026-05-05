import shutil

import typer
from InquirerPy import inquirer
from InquirerPy.enum import (
    INQUIRERPY_EMPTY_CIRCLE_SEQUENCE,
    INQUIRERPY_FILL_CIRCLE_SEQUENCE,
)
from rich.panel import Panel
from rich.prompt import Confirm

from taken.core import paths
from taken.core.config import is_config_exists
from taken.core.git import auto_commit_and_push
from taken.core.registry import read_registry, write_registry
from taken.models.registry import Registry, RegistryEntry
from taken.utils.console import console, err_console


def _resolve_selected(
    namespace_skill: str | None,
    registry: Registry,
) -> list[RegistryEntry]:
    """Return list of entries chosen by the user; raises typer.Exit on invalid input."""
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
        return [entry]

    choices = [
        {"name": f"{e.full_name}  [{e.source.value}]", "value": e.full_name}
        for e in sorted(registry.skills.values(), key=lambda e: e.full_name)
    ]
    selected_names: list[str] = inquirer.fuzzy(  # type: ignore[attr-defined]
        message="Select skills to remove:",
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

    return [e for name in selected_names if (e := registry.get(name)) is not None]


def remove(
    namespace_skill: str | None = typer.Argument(
        None,
        help="Skill to remove from registry, e.g. pradyothsp/my-skill. Omit for interactive picker.",
    ),
) -> None:
    """Remove a skill from ~/.taken/ registry and delete its files."""
    if not is_config_exists(paths.TAKEN_HOME):
        err_console.print(
            Panel(
                "Taken is not initialized. Run [bold]taken init[/bold] to get started.",
                title="[red]Not Initialized[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    registry = read_registry(paths.TAKEN_HOME)

    if not registry.skills:
        err_console.print(
            Panel(
                "No skills in your registry yet. Run [bold]taken add[/bold] to create one.",
                title="[red]Registry Empty[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    selected = _resolve_selected(namespace_skill, registry)

    removed: list[str] = []
    removed_names: list[str] = []
    skipped: list[str] = []

    for entry in selected:
        if not Confirm.ask(f"  Remove [bold]{entry.full_name}[/bold]?", default=False):
            skipped.append(entry.full_name)
            continue

        skill_dir = paths.TAKEN_HOME / "skills" / entry.namespace / entry.name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

        registry.remove(entry.full_name)
        removed.append(f"[red]✕[/red] [bold]{entry.full_name}[/bold]")
        removed_names.append(entry.full_name)

    if removed:
        write_registry(registry, paths.TAKEN_HOME)
        auto_commit_and_push(paths.TAKEN_HOME, f"remove: {' '.join(removed_names)}")

        lines = "\n".join(removed)
        console.print(
            Panel(
                lines,
                title="[green]Skills Removed[/green]",
                border_style="green",
                padding=(1, 2),
            )
        )
        console.print("[dim]Project copies in .agents/skills/ are unaffected.[/dim]")

    if not removed and not skipped:
        return

    if skipped and not removed:
        console.print("[dim]No skills removed.[/dim]")
