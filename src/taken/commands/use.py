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
from rich.prompt import Confirm

from taken.core.config import is_config_exists
from taken.core.hashing import compute_skill_hash
from taken.core.project import read_project_config, write_project_config
from taken.core.registry import read_registry
from taken.models.project import ProjectConfig, ProjectSkillEntry
from taken.models.registry import Registry, RegistryEntry
from taken.utils.console import console, err_console

TAKEN_HOME = Path.home() / ".taken"


def _resolve_selected(
    namespace_skill: str | None,
    registry: Registry,
) -> list[RegistryEntry]:
    """Return the list of skills the user chose; raises typer.Exit on invalid input."""
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

    return [e for name in selected_names if (e := registry.get(name)) is not None]


def use(
    namespace_skill: str | None = typer.Argument(
        None,
        help="Skill to copy into project, e.g. pradyothsp/hello-world. Omit for interactive picker.",
    ),
) -> None:
    """Copy skill(s) from ~/.taken/ into the current project's .agents/skills/ directory."""
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

    selected = _resolve_selected(namespace_skill, registry)

    project_config = read_project_config(Path.cwd())
    agents_dir = Path.cwd() / project_config.skills_dir
    agents_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    copied: list[str] = []
    skipped: list[str] = []

    for entry in selected:
        dst = agents_dir / entry.name
        existing = project_config.skills.get(entry.full_name)

        if dst.exists() and existing is not None:
            local_hash = compute_skill_hash(dst)
            if local_hash != existing.copied_hash:
                console.print(f"\n[yellow]⚠[/yellow]  [bold]{entry.name}[/bold] has local changes in your project.")
                if not Confirm.ask(f"  Overwrite [bold]{entry.name}[/bold]?", default=False):
                    skipped.append(entry.full_name)
                    continue

        _copy_skill(entry, dst, project_config, now)
        copied.append(f"[green]✓[/green] [bold]{entry.full_name}[/bold] → {project_config.skills_dir}/{entry.name}/")

    if not copied and not skipped:
        return

    write_project_config(project_config, Path.cwd())

    if copied:
        lines = "\n".join(copied) + "\n\n[dim]Tracked in .taken.yaml[/dim]"
        console.print(
            Panel(
                lines,
                title="[green]Skills Added[/green]",
                border_style="green",
                padding=(1, 2),
            )
        )
    if skipped:
        console.print(f"[dim]Skipped: {', '.join(skipped)}[/dim]")


def _copy_skill(
    entry: RegistryEntry,
    dst: Path,
    project_config: ProjectConfig,
    now: datetime,
) -> None:
    src = TAKEN_HOME / "skills" / entry.namespace / entry.name

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    project_config.skills[entry.full_name] = ProjectSkillEntry(
        copied_at=now,
        copied_hash=compute_skill_hash(dst),
    )
