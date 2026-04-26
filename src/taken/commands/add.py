import re
from datetime import datetime
from pathlib import Path

import typer
from rich.panel import Panel

from taken.core.config import is_config_exists, read_config
from taken.core.editor import open_in_editor
from taken.core.registry import read_registry, write_registry
from taken.core.skills import (
    adopt_skill,
    is_path_argument,
    lookup_lock_entry,
    scaffold_skill,
)
from taken.models.config import TakenConfig
from taken.models.registry import RegistryEntry, SkillSource
from taken.utils.console import console, err_console

TAKEN_HOME = Path.home() / ".taken"

_VALID_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def add(
    skill_or_path: str = typer.Argument(
        ..., help="Skill name to create, or path to existing skill folder to adopt"
    ),
) -> None:
    """Add a new personal skill or adopt an existing skill into taken management."""
    if not is_config_exists(TAKEN_HOME):
        err_console.print(
            Panel(
                "Taken is not initialized. Run [bold]taken init[/bold] to get started.",
                title="[red]Not Initialized[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    config = read_config(TAKEN_HOME)

    if is_path_argument(skill_or_path):
        _adopt_mode(skill_or_path, config)
    else:
        _create_mode(skill_or_path, config)


def _create_mode(name: str, config: TakenConfig) -> None:
    if "/" in name:
        err_console.print(
            Panel(
                f"Skill name must not contain a namespace. Got: [bold]{name}[/bold]\n"
                f"Your namespace [bold]{config.username}[/bold] is added automatically.\n"
                "Example: [bold]taken add my-skill[/bold]",
                title="[red]Invalid Skill Name[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    if not _VALID_NAME.match(name):
        err_console.print(
            Panel(
                f"[bold]{name}[/bold] is not a valid skill name.\n"
                "Use lowercase letters, numbers, hyphens, and underscores only.\n"
                "Must start with a letter or number.",
                title="[red]Invalid Skill Name[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    registry = read_registry(TAKEN_HOME)
    full_name = f"{config.username}/{name}"

    if registry.exists(full_name):
        err_console.print(
            Panel(
                f"Skill [bold]{full_name}[/bold] is already in your registry.\n"
                "Use [bold]taken list[/bold] to see it.",
                title="[red]Already Exists[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    try:
        skill_md = scaffold_skill(config.username, name, TAKEN_HOME)
    except FileExistsError:
        err_console.print(
            Panel(
                f"Skill directory already exists on disk but is not in the registry.\n"
                f"Path: [dim]{TAKEN_HOME}/skills/{config.username}/{name}[/dim]\n"
                "Run [bold]taken doctor[/bold] to repair registry drift.",
                title="[red]Directory Conflict[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    now = datetime.now()
    entry = RegistryEntry(
        namespace=config.username,
        name=name,
        source=SkillSource.PERSONAL,
        created_at=now,
        updated_at=now,
    )
    registry.add(entry)
    write_registry(registry, TAKEN_HOME)

    console.print(
        Panel(
            f"[green]✓[/green] Created [bold]{full_name}[/bold]\n"
            f"[green]✓[/green] Registered as [bold]personal[/bold] skill\n\n"
            f"[dim]Opening editor…[/dim]",
            title="[green]Skill Created[/green]",
            border_style="green",
            padding=(1, 2),
        )
    )

    open_in_editor(skill_md)


def _adopt_mode(path_str: str, config: TakenConfig) -> None:
    source_dir = Path(path_str).resolve()

    if not source_dir.is_dir():
        err_console.print(
            Panel(
                f"[bold]{path_str}[/bold] is not a directory.",
                title="[red]Invalid Path[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    name = source_dir.name
    lock_entry = lookup_lock_entry(name, Path.cwd())

    if lock_entry is not None:
        namespace = lock_entry.source.split("/")[0]
        source = SkillSource.NPX
        repo = lock_entry.source
        version = lock_entry.ref
        source_url = lock_entry.source_url
        skill_path = lock_entry.skill_path
        skill_folder_hash = lock_entry.skill_folder_hash
    else:
        namespace = config.username
        source = SkillSource.PERSONAL
        repo = None
        version = None
        source_url = None
        skill_path = None
        skill_folder_hash = None

    registry = read_registry(TAKEN_HOME)
    full_name = f"{namespace}/{name}"

    if registry.exists(full_name):
        err_console.print(
            Panel(
                f"Skill [bold]{full_name}[/bold] is already in your registry.\n"
                "Use [bold]taken list[/bold] to see it.",
                title="[red]Already Exists[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    try:
        adopt_skill(source_dir, namespace, name, TAKEN_HOME)
    except FileExistsError:
        err_console.print(
            Panel(
                f"Skill directory already exists at [dim]{TAKEN_HOME}/skills/{namespace}/{name}[/dim]\n"
                "Run [bold]taken doctor[/bold] to repair registry drift.",
                title="[red]Directory Conflict[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    now = datetime.now()
    entry = RegistryEntry(
        namespace=namespace,
        name=name,
        source=source,
        repo=repo,
        version=version,
        installed_at=now if source == SkillSource.NPX else None,
        created_at=now if source == SkillSource.PERSONAL else None,
        updated_at=now,
        source_url=source_url,
        skill_path=skill_path,
        skill_folder_hash=skill_folder_hash,
    )
    registry.add(entry)
    write_registry(registry, TAKEN_HOME)

    source_detail = f" ({repo})" if repo else ""
    console.print(
        Panel(
            f"[green]✓[/green] Adopted [bold]{name}[/bold] → [bold]{full_name}[/bold]\n"
            f"[green]✓[/green] Source: [bold]{source.value}[/bold]{source_detail}\n\n"
            f"[dim]Copied to ~/.taken/skills/{namespace}/{name}/[/dim]",
            title="[green]Skill Adopted[/green]",
            border_style="green",
            padding=(1, 2),
        )
    )
