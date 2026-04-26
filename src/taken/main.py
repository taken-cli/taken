import typer

from taken.commands.add import add
from taken.commands.init import init
from taken.commands.list import list as list_cmd

app = typer.Typer(
    name="taken",
    help="A very particular set of skills, managed.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.command("init")(init)
app.command("add")(add)
app.command("list")(list_cmd)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
