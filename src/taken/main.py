import typer

from taken.commands.add import add
from taken.commands.init import init
from taken.commands.list import list as list_cmd
from taken.commands.save import save
from taken.commands.use import use

app = typer.Typer(
    name="taken",
    help="A very particular set of skills, managed.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.command("init")(init)
app.command("add")(add)
app.command("list")(list_cmd)
app.command("use")(use)
app.command("save")(save)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
