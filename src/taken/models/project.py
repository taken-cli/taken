from datetime import datetime

from pydantic import BaseModel, Field


class ProjectSkillEntry(BaseModel):
    copied_at: datetime
    copied_hash: str


class ProjectConfig(BaseModel):
    version: int = 1
    skills_dir: str = ".agents/skills"
    skills: dict[str, ProjectSkillEntry] = Field(default_factory=dict)
