from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from ruamel.yaml import YAML

from taken.core import paths
from taken.models.config import MirrorMode, TakenConfig
from taken.models.project import ProjectConfig, ProjectSkillEntry, ProjectsState, SkillLayout

_yaml: Any = YAML()
_yaml.default_flow_style = False
_yaml.preserve_quotes = True

PROJECTS_FILE = "projects.yaml"
GITIGNORE_FILE = ".gitignore"
CURRENT_PROJECTS_VERSION = 1

# Upcasters migrate raw projects.yaml data one version at a time:
# _UPCASTERS[n] takes version-n data and returns version-(n+1) data.
# Add an entry here (and bump CURRENT_PROJECTS_VERSION) for every schema change.
_UPCASTERS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def get_projects_path(taken_home: Path) -> Path:
    return taken_home / PROJECTS_FILE


def _project_key(project_root: Path) -> str:
    return str(project_root.resolve())


def _upcast(data: dict[str, Any]) -> dict[str, Any]:
    version = int(data.get("version", 1))
    while version < CURRENT_PROJECTS_VERSION:
        data = _UPCASTERS[version](data)
        version += 1
        data["version"] = version
    return data


def _ensure_gitignored(taken_home: Path) -> None:
    """projects.yaml holds machine-local paths and hashes — keep it out of the synced ~/.taken repo."""
    gitignore = taken_home / GITIGNORE_FILE
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if PROJECTS_FILE in existing.splitlines():
        return
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    gitignore.write_text(f"{existing}{prefix}{PROJECTS_FILE}\n", encoding="utf-8")


def _serialize_project(config: ProjectConfig) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if config.mirror_mode is not None:
        data["mirror_mode"] = config.mirror_mode.value
    data["skills"] = {
        key: {
            "copied_at": entry.copied_at.isoformat(),
            "copied_hash": entry.copied_hash,
        }
        for key, entry in config.skills.items()
    }
    return data


def _deserialize_project(data: dict[str, Any]) -> ProjectConfig:
    raw_skills = cast(dict[str, dict[str, Any]], data.get("skills") or {})
    raw_mode = data.get("mirror_mode")
    return ProjectConfig(
        mirror_mode=MirrorMode(raw_mode) if raw_mode else None,
        skills={
            key: ProjectSkillEntry(
                copied_at=datetime.fromisoformat(entry["copied_at"]),
                copied_hash=entry.get("copied_hash", ""),
            )
            for key, entry in raw_skills.items()
        },
    )


def read_projects_state(taken_home: Path) -> ProjectsState:
    """Read ~/.taken/projects.yaml, upcasting older schema versions. Missing file → empty state."""
    path = get_projects_path(taken_home)
    if not path.exists():
        return ProjectsState()

    with path.open("r", encoding="utf-8") as f:
        data = cast(dict[str, Any] | None, _yaml.load(f))

    if not data:
        return ProjectsState()

    data = _upcast(dict(data))
    raw_projects = cast(dict[str, dict[str, Any]], data.get("projects") or {})
    return ProjectsState(
        version=CURRENT_PROJECTS_VERSION,
        projects={key: _deserialize_project(value or {}) for key, value in raw_projects.items()},
    )


def write_projects_state(state: ProjectsState, taken_home: Path) -> None:
    taken_home.mkdir(parents=True, exist_ok=True)
    _ensure_gitignored(taken_home)

    data: dict[str, Any] = {
        "version": CURRENT_PROJECTS_VERSION,
        "projects": {key: _serialize_project(project) for key, project in state.projects.items()},
    }

    with get_projects_path(taken_home).open("w", encoding="utf-8") as f:
        _yaml.dump(data, f)


def is_project_config_exists(project_root: Path, taken_home: Path | None = None) -> bool:
    home = taken_home or paths.TAKEN_HOME
    return _project_key(project_root) in read_projects_state(home).projects


def read_project_config(project_root: Path, taken_home: Path | None = None) -> ProjectConfig:
    """Return this project's state from ~/.taken/projects.yaml (empty if untracked)."""
    home = taken_home or paths.TAKEN_HOME
    return read_projects_state(home).projects.get(_project_key(project_root), ProjectConfig())


def write_project_config(config: ProjectConfig, project_root: Path, taken_home: Path | None = None) -> None:
    """Store this project's state in ~/.taken/projects.yaml, leaving other projects untouched."""
    home = taken_home or paths.TAKEN_HOME
    state = read_projects_state(home)
    state.projects[_project_key(project_root)] = config
    write_projects_state(state, home)


def resolve_layout(config: TakenConfig, project_config: ProjectConfig) -> SkillLayout:
    """Merge global skill placement settings with the project's overrides."""
    return SkillLayout(
        main_dir=config.skills.main_dir,
        mirror_dirs=tuple(config.skills.mirror_dirs),
        mirror_mode=project_config.mirror_mode or config.skills.mirror_mode,
    )
