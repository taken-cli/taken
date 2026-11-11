import shutil
import sys
from datetime import datetime
from pathlib import Path

import typer
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.enum import (
    INQUIRERPY_EMPTY_CIRCLE_SEQUENCE,
    INQUIRERPY_FILL_CIRCLE_SEQUENCE,
)
from rich.panel import Panel
from rich.prompt import Confirm

from taken.core import paths
from taken.core.config import is_config_exists, normalize_mirror_dir, read_config
from taken.core.hashing import compute_skill_hash
from taken.core.mirror import (
    MirrorResult,
    edited_copies,
    main_skill_dir,
    remove_path,
    remove_unselected_mirrors,
    sync_mirrors,
    untracked_paths,
)
from taken.core.project import read_project_config, resolve_layout, skill_layout, write_project_config
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
    mirror: list[str] = typer.Option(  # noqa: B008
        [],
        "--mirror",
        "-m",
        help="Mirror dir to link into (repeatable). Skips the prompt. Must be in `taken mirrors list`.",
    ),
    no_mirror: bool = typer.Option(
        False,
        "--no-mirror",
        help="Don't mirror into any agent dir. Skips the prompt.",
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

    chosen_dirs = _resolve_mirror_dirs(mirror, no_mirror, layout, selected, project_config)
    new_layout = layout.model_copy(update={"mirror_dirs": tuple(chosen_dirs)})

    now = datetime.now()
    copied: list[str] = []
    skipped: list[str] = []

    for entry in selected:
        existing = project_config.skills.get(entry.full_name)
        prev_layout = skill_layout(layout, existing)
        if not _confirm_overwrite(entry, project_root, prev_layout, new_layout, existing):
            skipped.append(entry.full_name)
            continue

        candidate_dirs = list(dict.fromkeys([*layout.mirror_dirs, *prev_layout.mirror_dirs]))
        removed = remove_unselected_mirrors(
            project_root,
            new_layout,
            candidate_dirs,
            entry.name,
            existing.copied_hash if existing else None,
        )
        results = _copy_skill(entry, project_root, new_layout, project_config, now)
        copied.append(_describe_copy(entry, project_root, new_layout, results, removed))

    if not copied and not skipped:
        return

    write_project_config(project_config, project_root)

    if copied:
        lines = "\n\n".join(copied) + "\n\n[dim]Tracked in ~/.taken/projects.yaml[/dim]"
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


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _default_mirror_dirs(
    available: list[str],
    selected: list[RegistryEntry],
    project_config: ProjectConfig,
) -> list[str]:
    """Pre-tick a single already-used skill's previous choice; otherwise everything."""
    if len(selected) == 1:
        existing = project_config.skills.get(selected[0].full_name)
        if existing is not None and existing.mirror_dirs is not None:
            return [d for d in available if d in existing.mirror_dirs]
    return available


def _resolve_mirror_dirs(
    mirror: list[str],
    no_mirror: bool,
    layout: SkillLayout,
    selected: list[RegistryEntry],
    project_config: ProjectConfig,
) -> list[str]:
    """Decide which mirror dirs to use: flags first, then the interactive picker, then defaults."""
    available = list(layout.mirror_dirs)

    if no_mirror:
        return []

    if mirror:
        chosen: list[str] = []
        for raw in mirror:
            try:
                normalized = normalize_mirror_dir(raw, layout.main_dir)
            except ValueError as e:
                err_console.print(Panel(str(e), title="[red]Invalid Mirror Dir[/red]", border_style="red"))
                raise typer.Exit(code=1) from e
            if normalized not in available:
                err_console.print(
                    Panel(
                        f"[bold]{normalized}[/bold] is not in your mirror list.\n"
                        f"Run [bold]taken mirrors add {normalized}[/bold] first.",
                        title="[red]Unknown Mirror Dir[/red]",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)
            chosen.append(normalized)
        return list(dict.fromkeys(chosen))

    if not available:
        return []

    preselected = _default_mirror_dirs(available, selected, project_config)
    if not _is_interactive():
        return preselected

    verb = "Symlink" if layout.mirror_mode == MirrorMode.SYMLINK else "Copy"
    picked: list[str] = inquirer.checkbox(  # type: ignore[attr-defined]
        message=f"{verb} into which folders?",
        choices=[Choice(value=d, name=d, enabled=d in preselected) for d in available],
        instruction="(space to toggle, enter to confirm — none is fine)",
        enabled_symbol=INQUIRERPY_FILL_CIRCLE_SEQUENCE,
        disabled_symbol=INQUIRERPY_EMPTY_CIRCLE_SEQUENCE,
    ).execute()
    return picked


def _confirm_overwrite(
    entry: RegistryEntry,
    project_root: Path,
    prev_layout: SkillLayout,
    new_layout: SkillLayout,
    existing: ProjectSkillEntry | None,
) -> bool:
    """Ask before clobbering local edits or folders taken did not create. Returns True to proceed."""
    if existing is not None:
        if edited_copies(project_root, prev_layout, entry.name, existing.copied_hash):
            console.print(f"\n[yellow]⚠[/yellow]  [bold]{entry.name}[/bold] has local changes in your project.")
            return Confirm.ask(f"  Overwrite [bold]{entry.name}[/bold]?", default=False)
        # Only newly chosen dirs can hold something taken didn't create.
        new_dirs = tuple(d for d in new_layout.mirror_dirs if d not in prev_layout.mirror_dirs)
        check_layout = new_layout.model_copy(update={"mirror_dirs": new_dirs})
    else:
        check_layout = new_layout

    foreign = untracked_paths(project_root, check_layout, entry.name)
    if foreign:
        listed = ", ".join(str(p.relative_to(project_root)) for p in foreign)
        console.print(f"\n[yellow]⚠[/yellow]  [bold]{listed}[/bold] already exists and was not created by taken.")
        return Confirm.ask(f"  Overwrite with [bold]{entry.full_name}[/bold]?", default=False)

    return True


def _describe_copy(
    entry: RegistryEntry,
    project_root: Path,
    layout: SkillLayout,
    results: list[MirrorResult],
    removed: list[Path],
) -> str:
    main_rel = f"{layout.main_dir}/{entry.name}"
    lines = [f"[green]✓[/green] [bold]{entry.full_name}[/bold] → {main_rel}/"]
    for result in results:
        rel = result.path.relative_to(project_root)
        if result.is_link:
            lines.append(f"  [cyan]🔗 {rel}[/cyan] → {main_rel}")
        elif result.fell_back:
            lines.append(f"  [yellow]📄 {rel}[/yellow] (copied — symlink not permitted)")
        else:
            lines.append(f"  [cyan]📄 {rel}[/cyan] (copy)")
    lines.extend(f"  [dim]✗ removed {path.relative_to(project_root)}[/dim]" for path in removed)
    if not results:
        lines.append("  [dim]not mirrored to any agent dir[/dim]")
    return "\n".join(lines)


def _copy_skill(
    entry: RegistryEntry,
    project_root: Path,
    layout: SkillLayout,
    project_config: ProjectConfig,
    now: datetime,
) -> list[MirrorResult]:
    """Copy registry skill into the main dir, then mirror it into the layout's dirs."""
    src = paths.TAKEN_HOME / "skills" / entry.namespace / entry.name
    dst = main_skill_dir(project_root, layout, entry.name)

    dst.parent.mkdir(parents=True, exist_ok=True)
    remove_path(dst)
    shutil.copytree(src, dst)
    results = sync_mirrors(project_root, layout, entry.name)

    project_config.skills[entry.full_name] = ProjectSkillEntry(
        copied_at=now,
        copied_hash=compute_skill_hash(dst),
        mirror_dirs=list(layout.mirror_dirs),
    )
    return results
