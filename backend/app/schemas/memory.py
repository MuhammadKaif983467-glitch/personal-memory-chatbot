"""Schemas for memories and retrieval output."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from pydantic import BaseModel, Field

MEMORY_TYPES = [
    "FACT", "PREFERENCE", "INTEREST", "GOAL", "PLAN", "EVENT", "DATE",
    "COMMITMENT", "DECISION", "RELATIONSHIP", "PROJECT", "EDUCATION", "WORK",
    "LOCATION", "CORRECTION", "HABIT", "OPINION", "CONVERSATION", "TEMPORARY",
    "OTHER",
]


class MemoryOut(BaseModel):
    id: int
    person_id: int
    person_name: str = ""
    content: str
    source_message_id: Optional[int] = None
    memory_type: str
    importance: float
    confidence: float
    status: str
    note: str = ""
    created_at: datetime
    updated_at: datetime


class MemoryCorrectRequest(BaseModel):
    correction: str = Field(min_length=1, description="The corrected memory value.")


class MemoryEditRequest(BaseModel):
    content: str = Field(min_length=1)


class MemoryCreateRequest(BaseModel):
    person_id: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=10_000)
    memory_type: str = "FACT"
    importance: float = Field(0.5, ge=0.0, le=1.0)
    confidence: float = Field(0.6, ge=0.0, le=1.0)


class MemorySearchRequest(BaseModel):
    query: str = ""
    person_id: Optional[int] = None
    memory_type: Optional[str] = None
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)
    limit: int = Field(20, ge=1, le=500)


class RetrievedMemoryOut(BaseModel):
    memory_id: int
    content: str
    memory_type: str
    confidence: float
    importance: float
    source_message_id: Optional[int] = None
    source_timestamp: Optional[datetime] = None
    similarity: float
    rank: int


class ConfidenceOut(BaseModel):
    level: str
    score: float
    signals: dict = Field(default_factory=dict)


def to_memory_out(memory, person_name: str = "") -> MemoryOut:
    return MemoryOut(
        id=memory.id,
        person_id=memory.person_id,
        person_name=person_name,
        content=memory.content,
        source_message_id=memory.source_message_id,
        memory_type=memory.memory_type,
        importance=memory.importance,
        confidence=memory.confidence,
        status=memory.status,
        note=memory.note,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


class MemoryVersionOut(BaseModel):
    id: int
    memory_id: int
    revision: int
    status: str
    content: str
    memory_type: str
    confidence: float
    importance: float
    source_message_id: Optional[int] = None
    note: str = ""
    actor: str = ""
    created_at: datetime


def to_memory_version_out(version) -> MemoryVersionOut:
    return MemoryVersionOut(
        id=version.id,
        memory_id=version.memory_id,
        revision=version.revision,
        status=version.status,
        content=version.content,
        memory_type=version.memory_type,
        confidence=version.confidence,
        importance=version.importance,
        source_message_id=version.source_message_id,
        note=version.note,
        actor=version.actor,
        created_at=version.created_at,
    )