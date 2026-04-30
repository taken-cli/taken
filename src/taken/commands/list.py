import typer
from rich.box import SIMPLE
from rich.panel import Panel
from rich.table import Table

from taken.core import paths
from taken.core.config import is_config_exists
from taken.core.registry import read_registry
from taken.models.registry import SkillSource
from taken.utils.console import console, err_console

_SOURCE_STYLE: dict[SkillSource, str] = {
    SkillSource.PERSONAL: "green",
    SkillSource.NPX: "blue",
    SkillSource.TAKEN: "magenta",
}


def list() -> None:
    """List all skills in the registry."""
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
        console.print("[yellow]No skills registered yet. Use [bold]taken add[/bold] to create one.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold", box=SIMPLE, padding=(0, 1))
    table.add_column("Skill", style="bold cyan", no_wrap=True)
    table.add_column("Source")
    table.add_column("Version")
    table.add_column("Date")

    for entry in sorted(registry.skills.values(), key=lambda e: e.full_name):
        style = _SOURCE_STYLE.get(entry.source, "")
        version = entry.version[:8] if entry.version else "—"
        date = entry.created_at or entry.installed_at
        date_str = date.strftime("%Y-%m-%d") if date else "—"
        table.add_row(
            entry.full_name,
            f"[{style}]{entry.source.value}[/{style}]",
            version,
            date_str,
        )

    console.print(table)
    count = len(registry.skills)
    console.print(f"[dim]{count} skill{'s' if count != 1 else ''}[/dim]")
