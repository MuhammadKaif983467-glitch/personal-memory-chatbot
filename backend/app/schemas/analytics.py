"""Schemas for unified search and conversation analysis (read-only)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(default="", max_length=500)
    project_id: Optional[int] = None
    person_id: Optional[int] = None
    conversation_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    memory_type: Optional[str] = None
    status: str = Field("active", max_length=20)
    limit: int = Field(20, ge=1, le=100)


class SearchMessageHit(BaseModel):
    message_id: int
    conversation_id: int
    conversation_title: str = ""
    sender: str = ""
    content: str
    timestamp: Optional[datetime] = None


class SearchMemoryHit(BaseModel):
    memory_id: int
    person_id: int
    person_name: str = ""
    content: str
    memory_type: str = ""
    confidence: float = 0.0
    status: str = "active"
    created_at: Optional[datetime] = None


class SearchConversationHit(BaseModel):
    conversation_id: int
    title: str = ""
    message_count: int = 0
    matched: bool = True


class SearchResponse(BaseModel):
    query: str
    messages: Sequence[SearchMessageHit] = []
    memories: Sequence[SearchMemoryHit] = []
    conversations: Sequence[SearchConversationHit] = []
    total: int = 0


class ParticipantCount(BaseModel):
    sender: str
    count: int


class TopicHit(BaseModel):
    value: str
    message_count: int
    sample: str = ""


class ConversationAnalysisOut(BaseModel):
    conversation_id: int
    person_id: int
    person_name: str = ""
    project_id: Optional[int] = None
    source: str = ""
    message_count: int = 0
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    participants: Sequence[ParticipantCount] = []
    top_topics: Sequence[TopicHit] = []
    decisions: Sequence[TopicHit] = []
    plans: Sequence[TopicHit] = []
    commitments: Sequence[TopicHit] = []