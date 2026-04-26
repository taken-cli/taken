from datetime import datetime
from pathlib import Path
from typing import Any, cast

from ruamel.yaml import YAML

from taken.models.project import ProjectConfig, ProjectSkillEntry

_yaml: Any = YAML()
_yaml.default_flow_style = False
_yaml.preserve_quotes = True

PROJECT_FILE = ".taken.yaml"


def get_project_config_path(project_root: Path) -> Path:
    return project_root / PROJECT_FILE


def is_project_config_exists(project_root: Path) -> bool:
    return get_project_config_path(project_root).exists()


def write_project_config(config: ProjectConfig, project_root: Path) -> None:
    path = get_project_config_path(project_root)

    data: dict[str, Any] = {
        "version": config.version,
        "skills_dir": config.skills_dir,
        "skills": {
            key: {
                "copied_at": entry.copied_at.isoformat(),
                "copied_hash": entry.copied_hash,
            }
            for key, entry in config.skills.items()
        },
    }

    with path.open("w", encoding="utf-8") as f:
        _yaml.dump(data, f)


def read_project_config(project_root: Path) -> ProjectConfig:
    path = get_project_config_path(project_root)

    if not path.exists():
        return ProjectConfig()

    with path.open("r", encoding="utf-8") as f:
        data = cast(dict[str, Any], _yaml.load(f))

    if not data:
        return ProjectConfig()

    raw_skills = cast(dict[str, dict[str, Any]], data.get("skills") or {})
    skills = {
        key: ProjectSkillEntry(
            copied_at=datetime.fromisoformat(entry["copied_at"]),
            copied_hash=entry.get("copied_hash", ""),
        )
        for key, entry in raw_skills.items()
    }

    return ProjectConfig(
        version=data.get("version", 1),
        skills_dir=data.get("skills_dir", ".agents/skills"),
        skills=skills,
    )
