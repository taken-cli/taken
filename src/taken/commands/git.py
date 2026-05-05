import typer

from taken.core import paths
from taken.core.git import run_passthrough


def git(ctx: typer.Context) -> None:
    """Run a git command in the taken home directory (~/.taken/)."""
    returncode = run_passthrough(paths.TAKEN_HOME, ctx.args)
    raise SystemExit(returncode)
