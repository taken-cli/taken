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
from rich.prompt import Prompt

from taken.core import paths
from taken.core.config import is_config_exists, read_config
from taken.core.git import auto_commit_and_push
from taken.core.hashing import compute_skill_hash
from taken.core.mirror import edited_copies, main_skill_dir, remove_path, sync_mirrors
from taken.core.project import is_project_config_exists, read_project_config, resolve_layout, write_project_config
from taken.core.registry import read_registry, write_registry
from taken.models.project import ProjectConfig, ProjectSkillEntry, SkillLayout
from taken.models.registry import Registry
from taken.utils.console import console, err_console


def _resolve_selected(
    namespace_skill: str | None,
    project_config: ProjectConfig,
) -> list[str]:
    """Return list of full_names chosen by the user; raises typer.Exit on invalid input."""
    if namespace_skill is not None:
        if namespace_skill not in project_config.skills:
            err_console.print(
                Panel(
                    f"[bold]{namespace_skill}[/bold] is not tracked in this project.\n"
                    "Run [bold]taken list[/bold] to see available skills.",
                    title="[red]Skill Not Found[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)
        return [namespace_skill]

    choices = [{"name": full_name, "value": full_name} for full_name in sorted(project_config.skills.keys())]
    selected: list[str] = inquirer.fuzzy(  # type: ignore[attr-defined]
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

    if not selected:
        raise typer.Exit(code=0)

    return selected


def _pick_source(name: str, edited: list[Path], project_root: Path) -> Path:
    """Choose which edited copy to save. Asks only when copies were edited differently."""
    hashes = {compute_skill_hash(p) for p in edited}
    if len(hashes) == 1:
        return edited[0]

    console.print(f"\n[yellow]⚠[/yellow]  [bold]{name}[/bold] was edited differently in more than one place:")
    for i, path in enumerate(edited, start=1):
        console.print(f"  [cyan]{i}[/cyan]  {path.relative_to(project_root)}")
    choice = Prompt.ask(
        "  Which copy should be saved?",
        choices=[str(i) for i in range(1, len(edited) + 1)],
        default="1",
    )
    return edited[int(choice) - 1]


def _process_skill(
    full_name: str,
    project_config: ProjectConfig,
    layout: SkillLayout,
    registry: Registry,
    now: datetime,
    saved: list[str],
    saved_names: list[str],
    no_changes: list[str],
) -> None:
    namespace, name = full_name.split("/", 1)
    project_root = Path.cwd()
    project_skill_dir = main_skill_dir(project_root, layout, name)
    registry_skill_dir = paths.TAKEN_HOME / "skills" / namespace / name

    existing = project_config.skills[full_name]
    edited = edited_copies(project_root, layout, name, existing.copied_hash)

    if not edited:
        no_changes.append(full_name)
        return

    source = _pick_source(name, edited, project_root)

    if registry_skill_dir.exists():
        shutil.rmtree(registry_skill_dir)
    shutil.copytree(source, registry_skill_dir)

    # Bring every project copy in line with what was saved.
    if source != project_skill_dir:
        remove_path(project_skill_dir)
        shutil.copytree(source, project_skill_dir)
    sync_mirrors(project_root, layout, name)

    new_hash = compute_skill_hash(registry_skill_dir)
    project_config.skills[full_name] = ProjectSkillEntry(
        copied_at=existing.copied_at,
        copied_hash=new_hash,
    )

    registry_entry = registry.get(full_name)
    if registry_entry is not None:
        registry_entry.updated_at = now

    saved.append(
        f"[green]✓[/green] [bold]{full_name}[/bold] ({source.relative_to(project_root)}) → "
        f"~/.taken/skills/{namespace}/{name}/"
    )
    saved_names.append(full_name)


def save(
    namespace_skill: str | None = typer.Argument(
        None,
        help="Skill to save back to registry, e.g. pradyothsp/my-skill. Omit for interactive picker.",
    ),
) -> None:
    """Push project edits back to ~/.taken/ registry — reverse of taken use."""
    if not is_config_exists(paths.TAKEN_HOME):
        err_console.print(
            Panel(
                "Taken is not initialized. Run [bold]taken init[/bold] to get started.",
                title="[red]Not Initialized[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    if not is_project_config_exists(Path.cwd()):
        err_console.print(
            Panel(
                "This directory is not tracked by taken yet.\n"
                "Run [bold]taken use[/bold] to add skills to this project first.",
                title="[red]Not a Taken Project[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    project_config = read_project_config(Path.cwd())

    if not project_config.skills:
        err_console.print(
            Panel(
                "No skills tracked in this project yet.\nRun [bold]taken use[/bold] to add skills first.",
                title="[red]No Skills Tracked[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    layout = resolve_layout(read_config(paths.TAKEN_HOME), project_config)
    selected = _resolve_selected(namespace_skill, project_config)
    registry = read_registry(paths.TAKEN_HOME)

    now = datetime.now()
    saved: list[str] = []
    saved_names: list[str] = []
    no_changes: list[str] = []

    for full_name in selected:
        _process_skill(full_name, project_config, layout, registry, now, saved, saved_names, no_changes)

    if not saved and not no_changes:
        return

    if saved:
        write_project_config(project_config, Path.cwd())
        write_registry(registry, paths.TAKEN_HOME)
        auto_commit_and_push(paths.TAKEN_HOME, f"save: {' '.join(saved_names)}")

        lines = "\n".join(saved) + "\n\n[dim]Registry and ~/.taken/projects.yaml updated[/dim]"
        console.print(
            Panel(
                lines,
                title="[green]Skills Saved[/green]",
                border_style="green",
                padding=(1, 2),
            )
        )

    if no_changes:
        console.print(f"[dim]No changes: {', '.join(no_changes)}[/dim]")
