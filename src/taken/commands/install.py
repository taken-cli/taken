import shutil
from datetime import datetime

import typer
from InquirerPy import inquirer
from InquirerPy.enum import INQUIRERPY_EMPTY_CIRCLE_SEQUENCE, INQUIRERPY_FILL_CIRCLE_SEQUENCE
from rich.panel import Panel

from taken.core import paths
from taken.core.config import is_config_exists
from taken.core.git import auto_commit_and_push
from taken.core.github import (
    GitHubSkill,
    discover_skills,
    download_skill,
    get_commit_sha,
    get_default_branch,
    normalize_source,
    parse_source,
)
from taken.core.registry import read_registry, write_registry
from taken.models.registry import RegistryEntry, SkillSource, VersionPin
from taken.utils.console import console, err_console


def _select_skills(skills: list[GitHubSkill]) -> list[GitHubSkill]:
    if len(skills) == 1:
        return skills

    choices = [{"name": s.name, "value": s} for s in skills]
    selected: list[GitHubSkill] = inquirer.fuzzy(  # type: ignore[attr-defined]
        message="Select skills to install:",
        choices=choices,
        multiselect=True,
        marker=INQUIRERPY_FILL_CIRCLE_SEQUENCE,
        marker_pl=INQUIRERPY_EMPTY_CIRCLE_SEQUENCE,
        instruction="(type to filter  space/tab to select  enter to confirm)",
        keybindings={"toggle": [{"key": "space"}, {"key": "tab"}]},
        validate=lambda x: len(x) > 0,
        invalid_message="Select at least one skill.",
    ).execute()
    return selected


def _filter_skills(
    skills: list[GitHubSkill],
    skill_filter: list[str],
    owner: str,
    repo: str,
) -> list[GitHubSkill]:
    """Apply name filter; raises typer.Exit(1) if no skills match."""
    if not skill_filter:
        return skills
    filtered = [s for s in skills if s.name in skill_filter]
    if not filtered:
        available = ", ".join(s.name for s in skills)
        err_console.print(
            Panel(
                f"No skill named [bold]{', '.join(skill_filter)}[/bold] found in [bold]{owner}/{repo}[/bold].\n"
                f"Available: [dim]{available}[/dim]",
                title="[red]Skill Not Found[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    return filtered


def _print_install_results(
    installed: list[str],
    skipped: list[str],
    owner: str,
    repo: str,
    sha: str,
    pin: bool,
) -> None:
    if installed:
        lines = "\n".join(f"[green]✓[/green] [bold]{n}[/bold]" for n in installed)
        lines += f"\n\n[dim]{owner}/{repo} @ {sha[:8]}[/dim]"
        if pin:
            lines += "\n[dim]Pinned to commit[/dim]"
        console.print(Panel(lines, title="[green]Skills Installed[/green]", border_style="green", padding=(1, 2)))
    if skipped:
        console.print(f"[dim]Already in registry (skipped): {', '.join(skipped)}[/dim]")
    if not installed and not skipped:
        console.print("[dim]Nothing installed.[/dim]")


def _fetch_github_skills(owner: str, repo: str, ref: str) -> tuple[str, list[GitHubSkill]]:
    """Resolve ref to a commit SHA and discover skills in the repo."""
    resolved_ref = ref if ref else get_default_branch(owner, repo)
    sha = get_commit_sha(owner, repo, resolved_ref)
    skills = discover_skills(owner, repo, sha)
    return sha, skills


def _install_skills(
    selected: list[GitHubSkill],
    owner: str,
    repo: str,
    sha: str,
    pin: bool,
) -> tuple[list[str], list[str]]:
    """Download and register each selected skill; return (installed, skipped)."""
    registry = read_registry(paths.TAKEN_HOME)
    installed: list[str] = []
    skipped: list[str] = []

    for gh_skill in selected:
        full_name = f"{owner}/{gh_skill.name}"
        dest = paths.TAKEN_HOME / "skills" / owner / gh_skill.name

        if registry.exists(full_name) or dest.exists():
            skipped.append(full_name)
            continue

        try:
            with console.status(f"[dim]Downloading {full_name}…[/dim]"):
                download_skill(owner, repo, gh_skill.skill_path, sha, dest)
        except Exception as e:
            err_console.print(Panel(str(e), title=f"[red]Failed: {full_name}[/red]", border_style="red"))
            if dest.exists():
                shutil.rmtree(dest)
            continue

        now = datetime.now()
        entry = RegistryEntry(
            namespace=owner,
            name=gh_skill.name,
            source=SkillSource.TAKEN,
            repo=f"{owner}/{repo}",
            version=sha,
            pin=VersionPin.PINNED if pin else VersionPin.FLOATING,
            installed_at=now,
            updated_at=now,
            source_url=f"https://github.com/{owner}/{repo}",
            skill_path=gh_skill.skill_path or None,
            skill_folder_hash=gh_skill.skill_folder_hash or None,
        )
        registry.add(entry)
        installed.append(full_name)

    if installed:
        write_registry(registry, paths.TAKEN_HOME)

    return installed, skipped


def install(
    source: str = typer.Argument(
        ...,
        metavar="source",
        help="GitHub repo, URL, or npx skills add command. E.g. vercel-labs/agent-skills",
    ),
    skill: list[str] = typer.Option(  # noqa: B008
        [],
        "--skill",
        "-s",
        help="Skill name(s) to install (repeatable). Alternative to owner/repo/skill path form.",
    ),
    ref: str = typer.Option(
        "", "--ref", metavar="REF", help="Branch, tag, or commit SHA (default: repo default branch)."
    ),
    pin: bool = typer.Option(False, "--pin", help="Pin to the exact commit SHA."),
) -> None:
    """Install one or more skills from a GitHub repository."""
    if not is_config_exists(paths.TAKEN_HOME):
        err_console.print(
            Panel(
                "Taken is not initialized. Run [bold]taken init[/bold] to get started.",
                title="[red]Not Initialized[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    try:
        normalized = normalize_source(source)
        owner, repo, path_filter = parse_source(normalized)
    except ValueError as e:
        err_console.print(Panel(str(e), title="[red]Invalid Source[/red]", border_style="red"))
        raise typer.Exit(code=1) from None

    # Merge skill selection: --skill flag wins; path filter is fallback; empty = all
    skill_filter: list[str] = list(skill) or ([path_filter] if path_filter else [])

    try:
        with console.status("[dim]Contacting GitHub…[/dim]"):
            sha, skills = _fetch_github_skills(owner, repo, ref)
    except FileNotFoundError:
        err_console.print(
            Panel(
                f"Repository [bold]{owner}/{repo}[/bold] not found on GitHub.\nCheck the name and try again.",
                title="[red]Not Found[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1) from None
    except PermissionError as e:
        err_console.print(
            Panel(
                f"{e}\n\nTip: set [bold]GITHUB_TOKEN[/bold] in your environment for higher rate limits.",
                title="[red]GitHub API Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        err_console.print(Panel(str(e), title="[red]Error[/red]", border_style="red"))
        raise typer.Exit(code=1) from e

    if not skills:
        err_console.print(
            Panel(
                f"No skills (SKILL.md files) found in [bold]{owner}/{repo}[/bold].",
                title="[red]No Skills Found[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    skills = _filter_skills(skills, skill_filter, owner, repo)
    selected = skills if skill_filter else _select_skills(skills)
    installed, skipped = _install_skills(selected, owner, repo, sha, pin)
    if installed:
        auto_commit_and_push(paths.TAKEN_HOME, f"install: {' '.join(installed)}")
    _print_install_results(installed, skipped, owner, repo, sha, pin)
