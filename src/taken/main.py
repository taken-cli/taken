from importlib.metadata import version as package_version

import typer

from taken.commands.add import add
from taken.commands.git import git
from taken.commands.init import init
from taken.commands.install import install
from taken.commands.list import list as list_cmd
from taken.commands.remove import remove
from taken.commands.save import save
from taken.commands.update import update
from taken.commands.use import use
from taken.utils.console import console

app = typer.Typer(
    name="taken",
    help="A very particular set of skills, managed.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"taken {package_version('taken-cli')}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the installed taken version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """A very particular set of skills, managed."""


app.command("init")(init)
app.command("add")(add)
app.command("install")(install)
app.command("list")(list_cmd)
app.command("use")(use)
app.command("save")(save)
app.command("update")(update)
app.command("remove")(remove)
app.command("git", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})(git)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
