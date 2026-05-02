import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GitHubSkill:
    name: str
    skill_path: str  # relative path within repo; "" = root-level skill
    skill_folder_hash: str  # GitHub tree SHA for this skill's directory


def _api_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "taken-cli/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _api_get(url: str) -> Any:
    req = urllib.request.Request(url, headers=_api_headers())
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 404:
            raise FileNotFoundError(f"Not found on GitHub: {url}") from e
        if e.code == 403:
            try:
                msg = json.loads(body).get("message", body)
            except json.JSONDecodeError:
                msg = body
            raise PermissionError(f"GitHub API error: {msg}") from e
        raise RuntimeError(f"GitHub API returned {e.code} for {url}") from e


def get_default_branch(owner: str, repo: str) -> str:
    data: dict[str, Any] = _api_get(f"https://api.github.com/repos/{owner}/{repo}")
    return str(data["default_branch"])


def get_commit_sha(owner: str, repo: str, ref: str) -> str:
    """Resolve a branch, tag, or ref to an exact commit SHA."""
    data: dict[str, Any] = _api_get(f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}")
    return str(data["sha"])


def discover_skills(owner: str, repo: str, sha: str) -> list[GitHubSkill]:
    """Return all skills found in the repo at the given commit SHA.

    A skill is any directory containing a SKILL.md file.
    """
    data: dict[str, Any] = _api_get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1")
    tree: list[dict[str, Any]] = data.get("tree", [])

    # Build path→SHA lookup for tree (directory) entries
    tree_shas: dict[str, str] = {item["path"]: str(item["sha"]) for item in tree if item.get("type") == "tree"}

    skills: list[GitHubSkill] = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path: str = item["path"]
        if path == "SKILL.md":
            # Root-level skill — use the commit SHA as the folder hash
            skills.append(GitHubSkill(name=repo, skill_path="", skill_folder_hash=sha))
        elif path.endswith("/SKILL.md"):
            skill_path = path[: -len("/SKILL.md")]
            name = skill_path.rsplit("/", 1)[-1]
            folder_hash = tree_shas.get(skill_path, "")
            skills.append(GitHubSkill(name=name, skill_path=skill_path, skill_folder_hash=folder_hash))

    return sorted(skills, key=lambda s: s.name)


def download_skill(owner: str, repo: str, skill_path: str, ref: str, dest: Path) -> None:
    """Download all files in skill_path from the repo into dest via the zipball API.

    The caller must ensure dest does not already exist.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{ref}"
    req = urllib.request.Request(url, headers=_api_headers())
    with urllib.request.urlopen(req) as resp:
        zip_data: bytes = resp.read()

    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        names = zf.namelist()
        if not names:
            raise RuntimeError("Downloaded zip archive is empty.")

        # Zipball top-level dir is "{owner}-{repo}-{sha_prefix}/"
        top_level = names[0].split("/")[0]
        prefix = f"{top_level}/{skill_path}/" if skill_path else f"{top_level}/"

        copied = 0
        for name in names:
            if not name.startswith(prefix) or name.endswith("/"):
                continue
            relative = name[len(prefix) :]
            if not relative:
                continue
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            copied += 1

        if copied == 0:
            raise RuntimeError(f"No files found for skill path '{skill_path}' in downloaded archive.")
