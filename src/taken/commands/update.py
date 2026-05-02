import shutil
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

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
from taken.core.github import discover_skills, download_skill, get_commit_sha, get_default_branch
from taken.core.hashing import compute_skill_hash
from taken.core.project import is_project_config_exists, read_project_config, write_project_config
from taken.core.registry import read_registry, write_registry
from taken.models.project import ProjectConfig, ProjectSkillEntry
from taken.models.registry import Registry, RegistryEntry, SkillSource, VersionPin
from taken.utils.console import console, err_console


class _GitHubRefreshResult(NamedTuple):
    refreshed_lines: list[str]
    is_registry_modified: bool


def _try_refresh_from_github(
    entry: RegistryEntry,
    registry: Registry,
    refreshed: list[str],
) -> bool:
    """Check GitHub for upstream changes to a taken-source skill and re-download if changed.

    Returns True if the registry skill was re-downloaded, False otherwise.
    Non-fatal: all errors are printed as warnings and return False.
    """
    if entry.repo is None:
        return False
    parts = entry.repo.split("/", 1)
    owner, repo_name = parts[0], parts[1]

    if entry.skill_folder_hash is None:
        return False

    try:
        with console.status(f"[dim]Checking GitHub for {entry.full_name}…[/dim]"):
            branch = get_default_branch(owner, repo_name)
            new_sha = get_commit_sha(owner, repo_name, branch)
            skills = discover_skills(owner, repo_name, new_sha)
    except Exception:
        console.print(f"[dim]⚠ Could not reach GitHub for {entry.full_name} — using local copy[/dim]")
        return False

    skill = next((s for s in skills if s.name == entry.name), None)
    if skill is None:
        console.print(f"[dim]⚠ {entry.full_name} not found in upstream repo — using local copy[/dim]")
        return False

    if skill.skill_folder_hash == entry.skill_folder_hash:
        return False

    skill_dir = paths.TAKEN_HOME / "skills" / entry.namespace / entry.name
    try:
        with console.status(f"[dim]Downloading updated {entry.full_name}…[/dim]"):
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
            download_skill(owner, repo_name, skill.skill_path, new_sha, skill_dir)
    except Exception as e:
        err_console.print(Panel(str(e), title=f"[red]Failed to refresh {entry.full_name}[/red]", border_style="red"))
        return False

    old_short = entry.version[:8] if entry.version else "?"
    registry.skills[entry.full_name].version = new_sha
    registry.skills[entry.full_name].skill_folder_hash = skill.skill_folder_hash
    registry.skills[entry.full_name].updated_at = datetime.now()
    refreshed.append(f"[blue]↑[/blue] [bold]{entry.full_name}[/bold] {old_short} → {new_sha[:8]}")
    return True


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


def _run_github_refresh_pass(selected: list[str]) -> _GitHubRefreshResult:
    """Check GitHub for upstream changes on all floating taken-source skills in selected."""
    registry = read_registry(paths.TAKEN_HOME)
    refreshed_from_github: list[str] = []
    is_registry_modified = False

    for full_name in selected:
        entry = registry.get(full_name)
        if (
            entry is not None
            and entry.source == SkillSource.TAKEN
            and entry.pin == VersionPin.FLOATING
            and entry.repo is not None
        ):
            modified = _try_refresh_from_github(entry, registry, refreshed_from_github)
            is_registry_modified = is_registry_modified or modified

    if is_registry_modified:
        write_registry(registry, paths.TAKEN_HOME)

    return _GitHubRefreshResult(refreshed_lines=refreshed_from_github, is_registry_modified=is_registry_modified)


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
    refresh_result = _run_github_refresh_pass(selected)
    refreshed_from_github = refresh_result.refreshed_lines

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

    if refreshed_from_github:
        lines = "\n".join(refreshed_from_github)
        console.print(
            Panel(
                lines,
                title="[blue]Refreshed from GitHub[/blue]",
                border_style="blue",
                padding=(1, 2),
            )
        )
