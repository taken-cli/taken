import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from taken.core.config import is_config_exists, write_config
from taken.core.registry import write_registry
from taken.models.config import TakenConfig
from taken.models.registry import Registry
from taken.utils.console import console, err_console

TAKEN_HOME = Path.home() / ".taken"


def _resolve_username() -> str:
    """
    Prompt the user to choose their namespace username via sequential prompts.
    Options: system username, git config name, or manual override.
    """
    # Gather candidates
    import getpass

    whoami = getpass.getuser()

    git_name: str | None = None
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        git_name = result.stdout.strip() or None
    except FileNotFoundError, subprocess.TimeoutExpired:
        git_name = None

    # Present options
    console.print("\n[bold]Choose your skill namespace username:[/bold]")
    console.print(f"  [cyan]1[/cyan]  System username   → [green]{whoami}[/green]")

    if git_name:
        console.print(f"  [cyan]2[/cyan]  Git config name  → [green]{git_name}[/green]")
        console.print("  [cyan]3[/cyan]  Enter manually")
    else:
        console.print(
            "  [cyan]2[/cyan]  Enter manually   [dim](git config name not found)[/dim]"
        )

    choice = Prompt.ask(
        "\nPick an option",
        choices=["1", "2", "3"] if git_name else ["1", "2"],
        default="1",
    )

    if choice == "1":
        return whoami
    elif choice == "2" and git_name:
        return git_name
    else:
        # Manual override
        username = Prompt.ask("Enter your username").strip()
        if not username:
            err_console.print(
                Panel(
                    "Username cannot be empty.",
                    title="[red]Error[/red]",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)
        return username


def _handle_existing_init() -> bool:
    """
    Handle the case where ~/.taken/ already exists.
    Prompts user to choose between resetting config only or full wipe.
    Returns True if we should proceed, False if user aborted.
    """
    err_console.print(
        Panel(
            "[yellow]Taken is already initialized at[/yellow] [bold]~/.taken/[/bold]\n\n"
            "Reinitializing will overwrite your config. Choose carefully.",
            title="[yellow]Already Initialized[/yellow]",
            border_style="yellow",
        )
    )

    proceed = Confirm.ask("Do you want to reinitialize?", default=False)
    if not proceed:
        console.print("[dim]Aborted. Nothing was changed.[/dim]")
        return False

    # Give user two options
    console.print("\n[bold]What would you like to reset?[/bold]")
    console.print(
        "  [cyan]1[/cyan]  Reset config only  [dim](keeps your skills and registry intact)[/dim]"
    )
    console.print(
        "  [cyan]2[/cyan]  Full wipe          [dim](deletes everything — skills, registry, config)[/dim]"
    )

    choice = Prompt.ask("\nPick an option", choices=["1", "2"], default="1")

    if choice == "2":
        confirm_wipe = Confirm.ask(
            "[red]This will delete ALL your skills and registry. Are you sure?[/red]",
            default=False,
        )
        if not confirm_wipe:
            console.print("[dim]Aborted. Nothing was changed.[/dim]")
            return False

        # Full wipe — delete ~/.taken/ entirely
        shutil.rmtree(TAKEN_HOME)
        console.print("[dim]Wiped ~/.taken/ — starting fresh.[/dim]")

    # Reset config only — just let init proceed and overwrite config.yaml
    return True


def init() -> None:
    """
    Initialize Taken — sets up ~/.taken/ with config.yaml and registry.yaml.
    """
    console.print(
        Panel(
            "[bold white]Welcome to Taken[/bold white]\n"
            "[dim]A very particular set of skills, managed.[/dim]",
            border_style="bright_blue",
            padding=(1, 4),
        )
    )

    # Handle existing init
    if is_config_exists(TAKEN_HOME):
        should_proceed = _handle_existing_init()
        if not should_proceed:
            raise typer.Exit(code=0)

    # Resolve username
    username = _resolve_username()

    # Create directory structure
    skills_dir = TAKEN_HOME / "skills" / username
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Write config
    config = TakenConfig(
        username=username,
        taken_home=TAKEN_HOME,
        initialized_at=datetime.now(),
    )
    write_config(config)

    # Write empty registry (only if it doesn't exist — preserve existing on config-only reset)
    from taken.core.registry import is_registry_exists

    if not is_registry_exists(TAKEN_HOME):
        write_registry(Registry(), TAKEN_HOME)

    # Success
    console.print(
        Panel(
            f"[green]✓[/green] Initialized at [bold]~/.taken/[/bold]\n"
            f"[green]✓[/green] Username set to [bold]{username}[/bold]\n\n"
            f"[dim]Your personal skills namespace: [bold]{username}/<skill-name>[/bold][/dim]",
            title="[green]Taken Initialized[/green]",
            border_style="green",
            padding=(1, 2),
        )
    )
