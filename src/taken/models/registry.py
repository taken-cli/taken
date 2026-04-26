from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class SkillSource(StrEnum):
    """Where the skill originated from."""

    PERSONAL = "personal"  # authored by the user via `taken add`
    NPX = "npx"  # installed via `npx skills add` and tracked by taken
    TAKEN = "taken"  # installed directly via `taken install`


class VersionPin(StrEnum):
    """Whether the skill tracks latest or is pinned to a specific version."""

    FLOATING = "floating"  # always update to latest
    PINNED = "pinned"  # locked to a specific version/commit


class RegistryEntry(BaseModel):
    """
    Represents a single skill entry in the registry.

    Designed to be forward-compatible — fields are optional where possible
    so future features (sidecar files, agent targeting, etc.) can be added
    without breaking existing registries.
    """

    # Identity
    namespace: str = Field(
        ...,
        description="Owner namespace (e.g. 'john' or 'vercel-labs').",
    )
    name: str = Field(
        ...,
        description="Skill name (e.g. 'cv-pipeline' or 'frontend-design').",
    )

    # Provenance
    source: SkillSource = Field(
        ...,
        description="Where this skill came from.",
    )
    repo: str | None = Field(
        default=None,
        description="Source repo for npx/taken-installed skills (e.g. 'vercel-labs/agent-skills').",
    )
    version: str | None = Field(
        default=None,
        description="Commit hash, tag, or version string at time of install.",
    )
    pin: VersionPin = Field(
        default=VersionPin.FLOATING,
        description="Whether this skill is pinned to a specific version or tracks latest.",
    )

    # Timestamps
    installed_at: datetime | None = Field(
        default=None,
        description="When the skill was first installed (npx/taken source only).",
    )
    created_at: datetime | None = Field(
        default=None,
        description="When the skill was created (personal source only).",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="When the skill was last updated.",
    )

    # Future expansion placeholders (stored but not yet actively used)
    agents: list[str] = Field(
        default_factory=list,
        description="Which agents this skill was installed for (e.g. ['claude-code', 'cursor']).",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional user notes about this skill.",
    )

    # NPX provenance enrichment (populated from global skills-lock)
    source_url: str | None = Field(
        default=None,
        description="Full git URL of the source repo.",
    )
    skill_path: str | None = Field(
        default=None,
        description="Path within the repo where the skill lives.",
    )
    skill_folder_hash: str | None = Field(
        default=None,
        description="GitHub tree SHA for change detection on update.",
    )

    @property
    def full_name(self) -> str:
        """Returns the fully qualified skill name: namespace/name."""
        return f"{self.namespace}/{self.name}"


class Registry(BaseModel):
    """
    Represents the full registry stored at ~/.taken/registry.yaml.

    The registry is the single source of truth for all installed skills.
    Keys are fully qualified skill names: 'namespace/skill-name'.
    """

    version: str = Field(
        default="1",
        description="Registry schema version. Used for future migrations.",
    )
    skills: dict[str, RegistryEntry] = Field(
        default_factory=dict,
        description="All tracked skills, keyed by 'namespace/skill-name'.",
    )

    def add(self, entry: RegistryEntry) -> None:
        """Add or overwrite a skill entry in the registry."""
        self.skills[entry.full_name] = entry

    def remove(self, full_name: str) -> bool:
        """Remove a skill by full name. Returns True if it existed."""
        if full_name in self.skills:
            del self.skills[full_name]
            return True
        return False

    def get(self, full_name: str) -> Optional[RegistryEntry]:
        """Retrieve a skill entry by full name."""
        return self.skills.get(full_name)

    def exists(self, full_name: str) -> bool:
        """Check if a skill is registered."""
        return full_name in self.skills
