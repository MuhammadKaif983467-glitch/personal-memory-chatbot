"""Schemas for people, profiles and writing style."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Fact


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    relationship: str
    # "ME" / "OTHER" within a two-person project; "" for legacy participants.
    participant_role: str = ""
    project_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    person_id: int
    interests: Sequence[Fact] = Field(default_factory=list)
    preferences: Sequence[Fact] = Field(default_factory=list)
    important_facts: Sequence[Fact] = Field(default_factory=list)
    communication_habits: Sequence[str] = Field(default_factory=list)
    topics: Sequence[dict] = Field(default_factory=list)
    generated_at: datetime


class StyleOut(BaseModel):
    person_id: int
    common_words: Sequence[str] = Field(default_factory=list)
    common_phrases: Sequence[str] = Field(default_factory=list)
    emoji_usage: dict = Field(default_factory=dict)
    sticker_usage: dict = Field(default_factory=dict)
    average_message_length: float = 0.0
    average_words_per_message: float = 0.0
    language_mix: dict = Field(default_factory=dict)
    tone: str = "neutral"
    punctuation_style: dict = Field(default_factory=dict)
    common_greetings: Sequence[str] = Field(default_factory=list)
    common_endings: Sequence[str] = Field(default_factory=list)
    analyzed_at: datetime


class MergePeopleRequest(BaseModel):
    from_person_id: int
    to_person_id: int


class MergeResult(BaseModel):
    from_person_id: int
    to_person_id: int
    moved_messages: int
    moved_conversations: int
    merged_profiles: bool


def to_person_out(person, message_count: int = 0) -> PersonOut:
    return PersonOut(
        id=person.id,
        name=person.name,
        relationship=person.relationship_type,
        participant_role=person.participant_role or "",
        project_id=getattr(person, "project_id", None),
        created_at=person.created_at,
        updated_at=person.updated_at,
        message_count=message_count,
    )