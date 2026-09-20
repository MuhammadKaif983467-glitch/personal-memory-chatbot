"""Normalized message types for the universal import pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Reaction:
    emoji: str
    user: str = ""


@dataclass
class NormalizedMessage:
    sender: str
    content: str
    timestamp: Optional[datetime] = None
    message_type: str = "text"
    original_content: str = ""
    is_system: bool = False
    is_edited: bool = False
    is_deleted: bool = False
    is_duplicate: bool = False
    media_filename: Optional[str] = None
    reactions: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    conversation_id: Optional[str] = None
    source_id: Optional[str] = None

    def __post_init__(self):
        if not self.original_content:
            self.original_content = self.content


@dataclass
class NormalizedConversation:
    title: str
    messages: list = field(default_factory=list)
    participants: list = field(default_factory=list)
    source_platform: str = "unknown"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


def normalize_messages(messages: list) -> list:
    """Convert NormalizedMessage list to ImportedMessage-compatible dicts."""
    from app.schemas.import_export import ImportedMessage

    result = []
    for msg in messages:
        if msg.is_deleted:
            continue
        ts = msg.timestamp.isoformat() if msg.timestamp else None
        metadata = {**msg.metadata}
        if msg.is_edited:
            metadata["is_edited"] = True
        if msg.reactions:
            metadata["reactions"] = [
                {"emoji": r.emoji, "user": r.user} for r in msg.reactions
            ]
        if msg.media_filename:
            metadata["media_filename"] = msg.media_filename
        result.append(ImportedMessage(
            sender=msg.sender,
            content=msg.content,
            timestamp=ts,
            message_type=msg.message_type,
            source_id=msg.source_id or "",
            metadata=metadata,
        ))
    return result
