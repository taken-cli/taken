from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML

from taken.models.registry import Registry, RegistryEntry, SkillSource, VersionPin

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.preserve_quotes = True

REGISTRY_FILE = "registry.yaml"


def get_registry_path(taken_home: Path) -> Path:
    return taken_home / REGISTRY_FILE


def _serialize_entry(entry: RegistryEntry) -> dict:
    """Convert a RegistryEntry to a YAML-serializable dict."""
    return {
        "namespace": entry.namespace,
        "name": entry.name,
        "source": entry.source.value,
        "repo": entry.repo,
        "version": entry.version,
        "pin": entry.pin.value,
        "installed_at": entry.installed_at.isoformat() if entry.installed_at else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        "agents": entry.agents,
        "notes": entry.notes,
        "source_url": entry.source_url,
        "skill_path": entry.skill_path,
        "skill_folder_hash": entry.skill_folder_hash,
    }


def _deserialize_entry(data: dict) -> RegistryEntry:
    """Convert a raw YAML dict back into a RegistryEntry."""

    def _parse_dt(val: str | None) -> datetime | None:
        return datetime.fromisoformat(val) if val else None

    return RegistryEntry(
        namespace=data["namespace"],
        name=data["name"],
        source=SkillSource(data["source"]),
        repo=data.get("repo"),
        version=data.get("version"),
        pin=VersionPin(data.get("pin", VersionPin.FLOATING)),
        installed_at=_parse_dt(data.get("installed_at")),
        created_at=_parse_dt(data.get("created_at")),
        updated_at=_parse_dt(data.get("updated_at")),
        agents=data.get("agents", []),
        notes=data.get("notes"),
        source_url=data.get("source_url"),
        skill_path=data.get("skill_path"),
        skill_folder_hash=data.get("skill_folder_hash"),
    )


def write_registry(registry: Registry, taken_home: Path) -> None:
    """
    Serialize Registry to ~/.taken/registry.yaml.
    Preserves comments on subsequent writes via ruamel.yaml.
    """
    path = get_registry_path(taken_home)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": registry.version,
        "skills": {
            key: _serialize_entry(entry) for key, entry in registry.skills.items()
        },
    }

    with path.open("w", encoding="utf-8") as f:
        _yaml.dump(data, f)


def read_registry(taken_home: Path) -> Registry:
    """
    Read and deserialize ~/.taken/registry.yaml into a Registry model.

    Returns an empty Registry if file does not exist — safe to call
    before init completes internally, but callers should prefer
    checking is_config_exists() first.
    """
    path = get_registry_path(taken_home)

    if not path.exists():
        return Registry()

    with path.open("r", encoding="utf-8") as f:
        data = _yaml.load(f)

    if not data:
        return Registry()

    skills = {
        key: _deserialize_entry(entry)
        for key, entry in (data.get("skills") or {}).items()
    }

    return Registry(
        version=data.get("version", "1"),
        skills=skills,
    )


def is_registry_exists(taken_home: Path) -> bool:
    """Returns True if ~/.taken/registry.yaml exists."""
    return get_registry_path(taken_home).exists()
