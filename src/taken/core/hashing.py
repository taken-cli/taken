import hashlib
from pathlib import Path


def compute_skill_hash(skill_dir: Path) -> str:
    """SHA-256 over all files in a skill folder — path + content, sorted.

    Same algorithm as skills.sh computedHash. Renames are detected because
    the relative path is included in the hash input.
    """
    files = sorted(
        (f for f in skill_dir.rglob("*") if f.is_file() and ".git" not in f.parts),
        key=lambda f: str(f.relative_to(skill_dir)),
    )

    h = hashlib.sha256()
    for f in files:
        h.update(str(f.relative_to(skill_dir)).encode())
        h.update(f.read_bytes())

    return h.hexdigest()
