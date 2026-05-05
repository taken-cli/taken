import subprocess
from pathlib import Path

from taken.utils.console import err_console


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def is_git_repo(taken_home: Path) -> bool:
    return (taken_home / ".git").is_dir()


def _has_changes(taken_home: Path) -> bool:
    result = _run(["git", "status", "--porcelain"], taken_home)
    return bool(result.stdout.strip())


def init_repo(taken_home: Path) -> None:
    """Initialize git repo in taken_home and make an initial commit."""
    try:
        already_exists = is_git_repo(taken_home)
        if not already_exists:
            _run(["git", "init"], taken_home)
        _run(["git", "add", "-A"], taken_home)
        message = "init: reinitialize taken home" if already_exists else "init: initialize taken home"
        _run(["git", "commit", "-m", message], taken_home)
    except FileNotFoundError:
        err_console.print("[dim]git not found — skipping version control setup[/dim]")


def commit(taken_home: Path, message: str) -> None:
    if not _has_changes(taken_home):
        return
    _run(["git", "add", "-A"], taken_home)
    _run(["git", "commit", "-m", message], taken_home)


def push(taken_home: Path) -> None:
    result = _run(["git", "push"], taken_home)
    if result.returncode != 0:
        err_console.print(f"[dim]git push failed: {result.stderr.strip()}[/dim]")


def auto_commit_and_push(taken_home: Path, message: str) -> None:
    """Read config and commit+push if enabled. Non-fatal on any git error."""
    try:
        from taken.core.config import read_config

        config = read_config(taken_home)
    except FileNotFoundError:
        return

    if not config.git.auto_commit:
        return

    try:
        commit(taken_home, message)
    except FileNotFoundError:
        err_console.print("[dim]git not found — skipping auto-commit[/dim]")
        return
    except Exception as e:
        err_console.print(f"[dim]git commit skipped: {e}[/dim]")
        return

    if not config.git.auto_push:
        return

    try:
        push(taken_home)
    except FileNotFoundError:
        err_console.print("[dim]git not found — skipping auto-push[/dim]")
    except Exception as e:
        err_console.print(f"[dim]git push failed: {e}[/dim]")


def run_passthrough(taken_home: Path, args: list[str]) -> int:
    """Run arbitrary git command in taken_home. Returns exit code."""
    try:
        result = subprocess.run(["git", *args], cwd=taken_home)
        return result.returncode
    except FileNotFoundError:
        err_console.print("[red]git not found[/red]")
        return 127
