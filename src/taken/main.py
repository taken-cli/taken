import typer

from taken.commands.init import init

app = typer.Typer(
    name="taken",
    help="A very particular set of skills, managed.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.command("init")(init)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
