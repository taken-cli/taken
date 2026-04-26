from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML

from taken.models.project import ProjectConfig, ProjectSkillEntry

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.preserve_quotes = True

PROJECT_FILE = ".taken.yaml"


def get_project_config_path(project_root: Path) -> Path:
    return project_root / PROJECT_FILE


def is_project_config_exists(project_root: Path) -> bool:
    return get_project_config_path(project_root).exists()


def write_project_config(config: ProjectConfig, project_root: Path) -> None:
    path = get_project_config_path(project_root)

    data: dict = {
        "version": config.version,
        "skills_dir": config.skills_dir,
        "skills": {
            key: {
                "copied_at": entry.copied_at.isoformat(),
                "registry_version": entry.registry_version,
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
        data = _yaml.load(f)

    if not data:
        return ProjectConfig()

    skills = {
        key: ProjectSkillEntry(
            copied_at=datetime.fromisoformat(entry["copied_at"]),
            registry_version=entry.get("registry_version"),
        )
        for key, entry in (data.get("skills") or {}).items()
    }

    return ProjectConfig(
        version=data.get("version", 1),
        skills_dir=data.get("skills_dir", ".agents/skills"),
        skills=skills,
    )
