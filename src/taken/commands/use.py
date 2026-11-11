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

from taken.core import paths
from taken.core.config import is_config_exists, read_config
from taken.core.hashing import compute_skill_hash
from taken.core.mirror import edited_copies, main_skill_dir, remove_path, sync_mirrors, untracked_paths
from taken.core.project import read_project_config, resolve_layout, write_project_config
from taken.core.registry import read_registry
from taken.models.config import MirrorMode
from taken.models.project import ProjectConfig, ProjectSkillEntry, SkillLayout
from taken.models.registry import Registry, RegistryEntry
from taken.utils.console import console, err_console


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
    mode: MirrorMode | None = typer.Option(  # noqa: B008
        None,
        "--mode",
        help="How to mirror into extra dirs like .claude/skills (symlink or copy). Remembered for this project.",
        case_sensitive=False,
    ),
) -> None:
    """Copy skill(s) from ~/.taken/ into the current project's skills dir and mirror them to agent dirs."""
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

    project_root = Path.cwd()
    project_config = read_project_config(project_root)
    if mode is not None:
        project_config.mirror_mode = mode
    layout = resolve_layout(read_config(paths.TAKEN_HOME), project_config)

    now = datetime.now()
    copied: list[str] = []
    skipped: list[str] = []

    for entry in selected:
        if not _confirm_overwrite(entry, project_root, layout, project_config):
            skipped.append(entry.full_name)
            continue

        fell_back = _copy_skill(entry, project_root, layout, project_config, now)
        copied.append(_describe_copy(entry, layout))
        for dst in fell_back:
            err_console.print(
                f"[yellow]⚠[/yellow]  Could not symlink [bold]{dst.relative_to(project_root)}[/bold] — copied instead."
            )

    if not copied and not skipped:
        return

    write_project_config(project_config, project_root)

    if copied:
        lines = "\n".join(copied) + "\n\n[dim]Tracked in ~/.taken/projects.yaml[/dim]"
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


def _confirm_overwrite(
    entry: RegistryEntry,
    project_root: Path,
    layout: SkillLayout,
    project_config: ProjectConfig,
) -> bool:
    """Ask before clobbering local edits or folders taken did not create. Returns True to proceed."""
    existing = project_config.skills.get(entry.full_name)

    if existing is not None:
        if edited_copies(project_root, layout, entry.name, existing.copied_hash):
            console.print(f"\n[yellow]⚠[/yellow]  [bold]{entry.name}[/bold] has local changes in your project.")
            return Confirm.ask(f"  Overwrite [bold]{entry.name}[/bold]?", default=False)
        return True

    foreign = untracked_paths(project_root, layout, entry.name)
    if foreign:
        listed = ", ".join(str(p.relative_to(project_root)) for p in foreign)
        console.print(f"\n[yellow]⚠[/yellow]  [bold]{listed}[/bold] already exists and was not created by taken.")
        return Confirm.ask(f"  Overwrite with [bold]{entry.full_name}[/bold]?", default=False)

    return True


def _describe_copy(entry: RegistryEntry, layout: SkillLayout) -> str:
    line = f"[green]✓[/green] [bold]{entry.full_name}[/bold] → {layout.main_dir}/{entry.name}/"
    if layout.mirror_dirs:
        verb = "linked" if layout.mirror_mode == MirrorMode.SYMLINK else "copied"
        targets = ", ".join(f"{d}/{entry.name}/" for d in layout.mirror_dirs)
        line += f"\n  [dim]{verb} to {targets}[/dim]"
    return line


def _copy_skill(
    entry: RegistryEntry,
    project_root: Path,
    layout: SkillLayout,
    project_config: ProjectConfig,
    now: datetime,
) -> list[Path]:
    """Copy registry skill into the main dir, then mirror it. Returns mirrors that fell back to copy."""
    src = paths.TAKEN_HOME / "skills" / entry.namespace / entry.name
    dst = main_skill_dir(project_root, layout, entry.name)

    dst.parent.mkdir(parents=True, exist_ok=True)
    remove_path(dst)
    shutil.copytree(src, dst)
    fell_back = sync_mirrors(project_root, layout, entry.name)

    project_config.skills[entry.full_name] = ProjectSkillEntry(
        copied_at=now,
        copied_hash=compute_skill_hash(dst),
    )
    return fell_back
