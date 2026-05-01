import shutil
from pathlib import Path

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
from taken.core.hashing import compute_skill_hash
from taken.core.project import is_project_config_exists, read_project_config, write_project_config
from taken.models.project import ProjectConfig, ProjectSkillEntry
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


def _process_skill(
    full_name: str,
    project_config: ProjectConfig,
    updated: list[str],
    skipped: list[str],
    up_to_date: list[str],
    suggest_save: list[str],
) -> None:
    namespace, name = full_name.split("/", 1)
    registry_skill_dir = paths.TAKEN_HOME / "skills" / namespace / name
    project_skill_dir = Path.cwd() / project_config.skills_dir / name

    if not registry_skill_dir.exists():
        err_console.print(
            Panel(
                f"Registry skill directory for [bold]{full_name}[/bold] not found.\nExpected: {registry_skill_dir}",
                title="[red]Registry Skill Missing[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    existing = project_config.skills[full_name]
    registry_hash = compute_skill_hash(registry_skill_dir)
    registry_changed = registry_hash != existing.copied_hash

    project_edited = False
    if project_skill_dir.exists():
        project_hash = compute_skill_hash(project_skill_dir)
        project_edited = project_hash != existing.copied_hash

    if not registry_changed and not project_edited:
        up_to_date.append(full_name)
        return

    if not registry_changed and project_edited:
        suggest_save.append(full_name)
        return

    if project_edited:
        console.print(f"\n[yellow]⚠[/yellow]  [bold]{name}[/bold] has local changes in your project.")
        if not Confirm.ask(f"  Overwrite [bold]{name}[/bold] with registry version?", default=False):
            skipped.append(full_name)
            return

    if project_skill_dir.exists():
        shutil.rmtree(project_skill_dir)
    shutil.copytree(registry_skill_dir, project_skill_dir)

    new_hash = compute_skill_hash(project_skill_dir)
    project_config.skills[full_name] = ProjectSkillEntry(
        copied_at=existing.copied_at,
        copied_hash=new_hash,
    )

    updated.append(f"[green]✓[/green] [bold]{full_name}[/bold] → {project_config.skills_dir}/{name}/")


def update(
    namespace_skill: str | None = typer.Argument(
        None,
        help="Skill to update from registry, e.g. pradyothsp/my-skill. Omit for interactive picker.",
    ),
) -> None:
    """Re-copy latest registry version of a skill into the current project."""
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
                "No [bold].taken.yaml[/bold] found in the current directory.\n"
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

    selected = _resolve_selected(namespace_skill, project_config)

    updated: list[str] = []
    skipped: list[str] = []
    up_to_date: list[str] = []
    suggest_save: list[str] = []

    for full_name in selected:
        _process_skill(full_name, project_config, updated, skipped, up_to_date, suggest_save)

    if updated:
        write_project_config(project_config, Path.cwd())
        lines = "\n".join(updated) + "\n\n[dim].taken.yaml updated[/dim]"
        console.print(
            Panel(
                lines,
                title="[green]Skills Updated[/green]",
                border_style="green",
                padding=(1, 2),
            )
        )

    if up_to_date:
        console.print(f"[dim]Already up to date: {', '.join(up_to_date)}[/dim]")

    if suggest_save:
        console.print(
            f"[dim]Local edits ahead of registry (use [bold]taken save[/bold] to push): {', '.join(suggest_save)}[/dim]"
        )

    if skipped:
        console.print(f"[dim]Skipped: {', '.join(skipped)}[/dim]")
