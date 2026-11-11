import typer
from rich.panel import Panel

from taken.core import paths
from taken.core.config import is_config_exists, normalize_mirror_dir, read_config, write_config
from taken.core.git import auto_commit_and_push
from taken.models.config import TakenConfig
from taken.utils.console import console, err_console

mirrors_app = typer.Typer(
    help="Manage the agent dirs (e.g. .claude/skills) that `taken use` can link skills into.",
    no_args_is_help=True,
)


def _load_config() -> TakenConfig:
    if not is_config_exists(paths.TAKEN_HOME):
        err_console.print(
            Panel(
                "Taken is not initialized. Run [bold]taken init[/bold] to get started.",
                title="[red]Not Initialized[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    return read_config(paths.TAKEN_HOME)


def _normalize_or_exit(raw: str, config: TakenConfig) -> str:
    try:
        return normalize_mirror_dir(raw, config.skills.main_dir)
    except ValueError as e:
        err_console.print(Panel(str(e), title="[red]Invalid Mirror Dir[/red]", border_style="red"))
        raise typer.Exit(code=1) from e


@mirrors_app.command("list")
def list_mirrors() -> None:
    """Show the main skills dir, mirror mode, and the mirror dirs offered by `taken use`."""
    config = _load_config()
    skills = config.skills
    console.print(f"[bold]Main dir:[/bold]    {skills.main_dir}")
    console.print(f"[bold]Mirror mode:[/bold] {skills.mirror_mode.value}")
    if not skills.mirror_dirs:
        console.print("[bold]Mirror dirs:[/bold] [dim]none — add one with[/dim] [bold]taken mirrors add <dir>[/bold]")
        return
    console.print("[bold]Mirror dirs:[/bold]")
    for d in skills.mirror_dirs:
        console.print(f"  • {d}")


@mirrors_app.command("add")
def add_mirror(
    directory: str = typer.Argument(..., help="Dir relative to the project root, e.g. .cursor/skills"),
) -> None:
    """Add a mirror dir that `taken use` will offer."""
    config = _load_config()
    normalized = _normalize_or_exit(directory, config)

    if normalized in config.skills.mirror_dirs:
        console.print(f"[dim]{normalized} is already in your mirror list.[/dim]")
        return

    config.skills.mirror_dirs.append(normalized)
    write_config(config)
    auto_commit_and_push(paths.TAKEN_HOME, f"mirrors: add {normalized}")
    console.print(f"[green]✓[/green] Added [bold]{normalized}[/bold] — `taken use` will offer it from now on.")


@mirrors_app.command("remove")
def remove_mirror(
    directory: str = typer.Argument(..., help="Mirror dir to stop offering, e.g. .cursor/skills"),
) -> None:
    """Stop offering a mirror dir. Existing links in projects are left in place."""
    config = _load_config()
    normalized = _normalize_or_exit(directory, config)

    if normalized not in config.skills.mirror_dirs:
        err_console.print(
            Panel(
                f"[bold]{normalized}[/bold] is not in your mirror list.\n"
                "Run [bold]taken mirrors list[/bold] to see it.",
                title="[red]Not Found[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    config.skills.mirror_dirs.remove(normalized)
    write_config(config)
    auto_commit_and_push(paths.TAKEN_HOME, f"mirrors: remove {normalized}")
    console.print(
        f"[green]✓[/green] Removed [bold]{normalized}[/bold].\n"
        "[dim]Existing links in projects stay; re-run `taken use` in a project to drop them.[/dim]"
    )
