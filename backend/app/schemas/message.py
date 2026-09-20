"""Schemas for messages and conversations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    title: str
    source: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    message_count: int = 0


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    person_id: Optional[int] = None
    sender: str
    content: str
    original_content: str
    timestamp: Optional[datetime] = None
    message_type: str
    is_duplicate: bool
    is_spam: bool
    language: str
    metadata: dict = {}


class ConversationDeleteResult(BaseModel):
    """Result of deleting a conversation.

    Memories are handled explicitly rather than silently: every memory whose
    source message lives in the deleted conversation is retired and its
    embedding removed, unless another memory depends on it (a correction chain)
    or it is already retired - those are preserved and counted as such.
    """

    conversation_id: int
    messages_deleted: int
    memories_deleted: int
    memories_preserved: int


def to_conversation_out(conversation, message_count: int) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        person_id=conversation.person_id,
        title=conversation.title,
        source=conversation.source,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        message_count=message_count,
    )


def to_message_out(message) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        person_id=message.person_id,
        sender=message.sender,
        content=message.content,
        original_content=message.original_content,
        timestamp=message.timestamp,
        message_type=message.message_type,
        is_duplicate=message.is_duplicate,
        is_spam=message.is_spam,
        language=message.language,
        metadata=message.msg_metadata or {},
    )