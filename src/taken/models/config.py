from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class GitConfig(BaseModel):
    auto_commit: bool = True
    auto_push: bool = True


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

    model_config = {"arbitrary_types_allowed": True}
