import json
import shutil
from pathlib import Path

from pydantic import BaseModel

_SKILL_TEMPLATE = """\
---
name: {name}
description: A short description of what this skill does.
---

Write your skill instructions here. Describe what the AI agent should do, step by step.
"""


class LockEntry(BaseModel):
    """Merged result from project + global skills-lock files."""

    source: str
    source_type: str
    ref: str
    computed_hash: str | None = None
    source_url: str | None = None
    skill_path: str | None = None
    skill_folder_hash: str | None = None


def is_path_argument(arg: str) -> bool:
    """Returns True if arg resolves to an existing directory on disk."""
    p = Path(arg)
    return p.exists() and p.is_dir()


def read_project_lock(cwd: Path) -> dict[str, dict]:
    """Read ./skills-lock.json (project-level, version 1).

    Returns empty dict if the file does not exist or is malformed.
    """
    lock_path = cwd / "skills-lock.json"
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        return dict(data.get("skills", {}))
    except FileNotFoundError, json.JSONDecodeError, KeyError, TypeError:
        return {}


def read_global_lock() -> dict[str, dict]:
    """Read ~/.agents/.skill-lock.json (global, version 3).

    Returns empty dict if the file does not exist or is malformed.
    """
    lock_path = Path.home() / ".agents" / ".skill-lock.json"
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        return dict(data.get("skills", {}))
    except FileNotFoundError, json.JSONDecodeError, KeyError, TypeError:
        return {}


def lookup_lock_entry(skill_name: str, cwd: Path) -> LockEntry | None:
    """Look up a skill in both lock files and return merged LockEntry.

    Project lock is checked first; global lock enriches with richer fields.
    Returns None if the skill is not found in either lock.
    """
    project = read_project_lock(cwd).get(skill_name)
    global_ = read_global_lock().get(skill_name)

    if project is None and global_ is None:
        return None

    base = project or global_
    if base is None:
        return None

    return LockEntry(
        source=base.get("source", ""),
        source_type=base.get("sourceType", "github"),
        ref=base.get("ref", "main"),
        computed_hash=(project or {}).get("computedHash"),
        source_url=(global_ or {}).get("sourceUrl"),
        skill_path=(global_ or {}).get("skillPath"),
        skill_folder_hash=(global_ or {}).get("skillFolderHash"),
    )


def scaffold_skill(namespace: str, name: str, taken_home: Path) -> Path:
    """Create ~/.taken/skills/<namespace>/<name>/SKILL.md from template.

    Returns the path to the created SKILL.md.
    Raises FileExistsError if the destination directory already exists.
    """
    dest_dir = taken_home / "skills" / namespace / name
    if dest_dir.exists():
        raise FileExistsError(f"Skill directory already exists: {dest_dir}")

    dest_dir.mkdir(parents=True, exist_ok=False)
    skill_md = dest_dir / "SKILL.md"
    skill_md.write_text(_SKILL_TEMPLATE.format(name=name), encoding="utf-8")
    return skill_md


def adopt_skill(source_dir: Path, namespace: str, name: str, taken_home: Path) -> Path:
    """Copy source_dir to ~/.taken/skills/<namespace>/<name>/.

    Returns the path to the copied SKILL.md.
    Raises FileExistsError if the destination already exists.
    """
    dest_dir = taken_home / "skills" / namespace / name
    if dest_dir.exists():
        raise FileExistsError(f"Skill directory already exists: {dest_dir}")

    shutil.copytree(source_dir, dest_dir)
    return dest_dir / "SKILL.md"
