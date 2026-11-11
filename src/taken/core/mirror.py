import os
import shutil
from pathlib import Path

from taken.core.hashing import compute_skill_hash
from taken.models.config import MirrorMode
from taken.models.project import SkillLayout


def main_skill_dir(project_root: Path, layout: SkillLayout, name: str) -> Path:
    """The tracked copy of a skill inside the project (e.g. .agents/skills/<name>)."""
    return project_root / layout.main_dir / name


def mirror_skill_dirs(project_root: Path, layout: SkillLayout, name: str) -> list[Path]:
    """Mirror locations of a skill inside the project (e.g. .claude/skills/<name>)."""
    main = main_skill_dir(project_root, layout, name)
    return [d for d in (project_root / m / name for m in layout.mirror_dirs) if d != main]


def is_managed_link(path: Path, main: Path) -> bool:
    """True if path is a symlink that resolves to the main copy."""
    return path.is_symlink() and path.resolve() == main.resolve()


def remove_path(path: Path) -> None:
    """Remove a file, symlink (without touching its target), or directory tree."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def sync_mirrors(project_root: Path, layout: SkillLayout, name: str) -> list[Path]:
    """
    Recreate every mirror of a skill from the main copy, using the layout's mirror mode.

    Symlinks are relative, so they keep working when the project is moved or cloned.
    If a symlink cannot be created (e.g. Windows without privileges), falls back to a copy.
    Returns the mirrors that fell back from symlink to copy.
    """
    main = main_skill_dir(project_root, layout, name)
    fell_back: list[Path] = []

    for dst in mirror_skill_dirs(project_root, layout, name):
        dst.parent.mkdir(parents=True, exist_ok=True)
        remove_path(dst)
        if layout.mirror_mode == MirrorMode.SYMLINK:
            try:
                dst.symlink_to(os.path.relpath(main, dst.parent), target_is_directory=True)
                continue
            except OSError:
                fell_back.append(dst)
        shutil.copytree(main, dst)

    return fell_back


def real_copies(project_root: Path, layout: SkillLayout, name: str) -> list[Path]:
    """Existing folders that hold real files for a skill (main + copied mirrors). Symlinks are excluded."""
    candidates = [main_skill_dir(project_root, layout, name), *mirror_skill_dirs(project_root, layout, name)]
    return [p for p in candidates if p.is_dir() and not p.is_symlink()]


def edited_copies(project_root: Path, layout: SkillLayout, name: str, baseline_hash: str) -> list[Path]:
    """Real copies whose contents differ from the hash recorded when taken last wrote them."""
    return [p for p in real_copies(project_root, layout, name) if compute_skill_hash(p) != baseline_hash]


def untracked_paths(project_root: Path, layout: SkillLayout, name: str) -> list[Path]:
    """Mirror locations already occupied by something taken did not create (ignores our own symlinks)."""
    main = main_skill_dir(project_root, layout, name)
    return [
        p
        for p in mirror_skill_dirs(project_root, layout, name)
        if (p.exists() or p.is_symlink()) and not is_managed_link(p, main)
    ]
