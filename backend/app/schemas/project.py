"""Project (workspace) schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.exceptions import ImportValidationError
from app.schemas.person import PersonOut

ME_ROLE = "ME"
OTHER_ROLE = "OTHER"


class ProjectParticipantIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    # "me" / "other" marks the user's own side in the two-person project.
    role: str = "other"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Project name")
    participants: list[ProjectParticipantIn] = Field(
        default_factory=list,
        description="Exactly two participants (one 'me', one 'other') for a two-person project.",
    )

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        name = str(value).strip()
        if not name:
            raise ImportValidationError("Project name cannot be empty or whitespace-only.")
        return name

    @model_validator(mode="after")
    def _validate_participants(self) -> "ProjectCreate":
        if not self.participants:
            return self
        if len(self.participants) != 2:
            raise ImportValidationError("A two-person project needs exactly two participants.")
        names = [p.name.strip() for p in self.participants]
        if any(not n for n in names):
            raise ImportValidationError("Participant names cannot be empty.")
        if len(set(n.casefold() for n in names)) != 2:
            raise ImportValidationError("Participant names must be different.")
        me_count = sum(1 for p in self.participants if p.role.strip().casefold() in ("me", "self", ME_ROLE.casefold()))
        if me_count != 1:
            raise ImportValidationError("Exactly one participant must be marked as 'me'.")
        return self


class ProjectOut(BaseModel):
    id: int
    name: str
    user_id: str = "local"
    created_at: datetime
    stats: dict


class ProjectDetailOut(ProjectOut):
    participants: Sequence[PersonOut] = []


class ProjectDeleteResult(BaseModel):
    project_id: int
    deleted_persons: int = 0
    deleted_conversations: int = 0
    deleted_messages: int = 0
    deleted_memories: int = 0
    deleted_vectors: int = 0
    deleted_embeddings: int = 0