import os
import shutil
from pathlib import Path
from typing import NamedTuple

from taken.core.hashing import compute_skill_hash
from taken.models.config import MirrorMode
from taken.models.project import SkillLayout


class MirrorResult(NamedTuple):
    """Outcome of mirroring one skill into one mirror dir."""

    path: Path
    is_link: bool
    fell_back: bool  # wanted a symlink but had to copy


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


def sync_mirrors(project_root: Path, layout: SkillLayout, name: str) -> list[MirrorResult]:
    """
    Recreate every mirror of a skill from the main copy, using the layout's mirror mode.

    Symlinks are relative, so they keep working when the project is moved or cloned.
    If a symlink cannot be created (e.g. Windows without privileges), falls back to a copy.
    """
    main = main_skill_dir(project_root, layout, name)
    results: list[MirrorResult] = []

    for dst in mirror_skill_dirs(project_root, layout, name):
        dst.parent.mkdir(parents=True, exist_ok=True)
        remove_path(dst)
        fell_back = False
        if layout.mirror_mode == MirrorMode.SYMLINK:
            try:
                dst.symlink_to(os.path.relpath(main, dst.parent), target_is_directory=True)
                results.append(MirrorResult(path=dst, is_link=True, fell_back=False))
                continue
            except OSError:
                fell_back = True
        shutil.copytree(main, dst)
        results.append(MirrorResult(path=dst, is_link=False, fell_back=fell_back))

    return results


def remove_unselected_mirrors(
    project_root: Path,
    layout: SkillLayout,
    candidate_dirs: list[str],
    name: str,
    baseline_hash: str | None,
) -> list[Path]:
    """
    Remove this skill from candidate mirror dirs that are not in the layout.

    Only removes what taken owns: symlinks to the main copy, or copies that still match
    the last-written hash. Anything edited or foreign is left alone. Returns removed paths.
    """
    main = main_skill_dir(project_root, layout, name)
    removed: list[Path] = []
    for d in candidate_dirs:
        if d in layout.mirror_dirs:
            continue
        path = project_root / d / name
        if path == main:
            continue
        is_ours = is_managed_link(path, main) or (
            baseline_hash is not None
            and path.is_dir()
            and not path.is_symlink()
            and compute_skill_hash(path) == baseline_hash
        )
        if is_ours:
            remove_path(path)
            removed.append(path)
    return removed


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
