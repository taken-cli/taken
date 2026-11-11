from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class GitConfig(BaseModel):
    auto_commit: bool = True
    auto_push: bool = True


class MirrorMode(StrEnum):
    """How skills are mirrored from the main skills dir into other agent dirs."""

    SYMLINK = "symlink"  # relative symlink pointing at the main copy
    COPY = "copy"  # full independent copy


class SkillsConfig(BaseModel):
    """Where skills are placed inside a project when running `taken use`."""

    main_dir: str = Field(
        default=".agents/skills",
        description="Primary skills directory, relative to the project root. This copy is the tracked one.",
    )
    mirror_dirs: list[str] = Field(
        default_factory=lambda: [".claude/skills"],
        description="Extra directories (relative to the project root) that mirror the main skills dir.",
    )
    mirror_mode: MirrorMode = Field(
        default=MirrorMode.SYMLINK,
        description="Default mirror mode for all projects. Can be overridden per project.",
    )


class TakenConfig(BaseModel):
    """
    Represents the user configuration stored at ~/.taken/config.yaml.

    This is the user-level config — set once during `taken init` and
    rarely modified after. It holds identity and preference info.
    """

    username: str = Field(
        ...,
        description="The namespace used for personal skills (e.g. 'john').",
    )
    taken_home: Path = Field(
        default=Path.home() / ".taken",
        description="Absolute path to the taken home directory.",
    )
    initialized_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of when `taken init` was first run.",
    )
    version: str = Field(
        default="1",
        description="Config schema version. Used for future migrations.",
    )
    git: GitConfig = Field(
        default_factory=GitConfig,
        description="Git version control settings for ~/.taken/.",
    )
    skills: SkillsConfig = Field(
        default_factory=SkillsConfig,
        description="Project skill placement settings (main dir, mirrors, mirror mode).",
    )

    model_config = {"arbitrary_types_allowed": True}
