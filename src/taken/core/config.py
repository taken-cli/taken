from pathlib import Path

from ruamel.yaml import YAML

from taken.models.config import TakenConfig

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.preserve_quotes = True

CONFIG_FILE = "config.yaml"


def get_config_path(taken_home: Path) -> Path:
    return taken_home / CONFIG_FILE


def write_config(config: TakenConfig) -> None:
    """
    Serialize TakenConfig to ~/.taken/config.yaml.
    Uses ruamel.yaml to preserve comments on subsequent writes.
    """
    path = get_config_path(config.taken_home)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": config.version,
        "username": config.username,
        "taken_home": str(config.taken_home),
        "initialized_at": config.initialized_at.isoformat(),
    }

    with path.open("w", encoding="utf-8") as f:
        _yaml.dump(data, f)


def read_config(taken_home: Path | None = None) -> TakenConfig:
    """
    Read and deserialize ~/.taken/config.yaml into a TakenConfig model.

    Raises FileNotFoundError if config does not exist —
    callers should handle this and prompt user to run `taken init`.
    """
    home = taken_home or Path.home() / ".taken"
    path = get_config_path(home)

    if not path.exists():
        raise FileNotFoundError(
            f"Taken config not found at {path}. Run `taken init` to get started."
        )

    with path.open("r", encoding="utf-8") as f:
        data = _yaml.load(f)

    return TakenConfig(
        version=data.get("version", "1"),
        username=data["username"],
        taken_home=Path(data.get("taken_home", str(home))),
        initialized_at=data.get("initialized_at"),
    )


def is_config_exists(taken_home: Path) -> bool:
    return get_config_path(taken_home).exists()
