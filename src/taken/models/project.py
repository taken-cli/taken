from datetime import datetime

from pydantic import BaseModel, Field

from taken.models.config import MirrorMode


class ProjectSkillEntry(BaseModel):
    copied_at: datetime
    copied_hash: str


class ProjectConfig(BaseModel):
    """
    Per-project state for one project, stored in ~/.taken/projects.yaml.

    Nothing is written inside the project itself — this is personal,
    machine-local tracking of which registry skills were copied where.
    """

    mirror_mode: MirrorMode | None = Field(
        default=None,
        description="Per-project override of the global mirror mode. None means use the global default.",
    )
    skills: dict[str, ProjectSkillEntry] = Field(
        default_factory=dict,
        description="Skills copied into this project, keyed by 'namespace/skill-name'.",
    )


class ProjectsState(BaseModel):
    """Represents ~/.taken/projects.yaml — every project taken has copied skills into."""

    version: int = Field(
        default=1,
        description="Projects file schema version. Older versions are upcast on read.",
    )
    projects: dict[str, ProjectConfig] = Field(
        default_factory=dict,
        description="Per-project state keyed by absolute project root path.",
    )


class SkillLayout(BaseModel):
    """Effective placement of skills in a project: global config merged with project overrides."""

    model_config = {"frozen": True}

    main_dir: str
    mirror_dirs: tuple[str, ...]
    mirror_mode: MirrorMode
