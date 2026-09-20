"""Schemas for the chat endpoint."""

from __future__ import annotations

from typing import Optional, Sequence

from pydantic import BaseModel, Field

from app.schemas.memory import ConfidenceOut, RetrievedMemoryOut


class LearnedMemoryOut(BaseModel):
    """Result of the current-conversation learning pass on a chat turn.

    outcome is one of NEW_MEMORY / UPDATED_MEMORY / CORRECTION / NO_MEMORY.
    When a memory was created or corrected, ``memory_id`` and ``content`` are
    populated; ``reason`` explains why nothing was stored otherwise.
    """

    outcome: str
    memory_id: Optional[int] = None
    person_id: Optional[int] = None
    content: str = ""
    memory_type: str = ""
    superseded_memory_id: Optional[int] = None
    reason: str = ""


class PendingMemoryOut(BaseModel):
    """A proposed memory awaiting user confirmation (memory_mode="ask").

    Nothing is stored until the user confirms. ``message_id`` identifies the
    source chat turn so confirmation happens without duplicating text.
    """

    message_id: int
    person_id: int
    person_name: str = ""
    content: str
    memory_type: str
    confidence: float
    importance: float


class MemoryConfirmRequest(BaseModel):
    message_id: int = Field(gt=0)
    person_id: int = Field(gt=0, description="The person who the memory is about (the ME participant).")
    action: str = Field("save", pattern="^(save|discard|edit)$")
    content: Optional[str] = Field(
        None, max_length=10_000, description="Edited text used when action='edit'."
    )
    memory_type: Optional[str] = Field(
        None, max_length=50, description="Memory type used when action='edit' (defaults to FACT)."
    )


class MemoryConfirmOut(BaseModel):
    saved: bool
    action: str
    memory_id: Optional[int] = None
    content: str = ""
    memory_type: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    person_id: Optional[int] = None
    conversation_id: Optional[int] = None
    sender_name: str = "me"
    debug: bool = False


class MemorySourceOut(BaseModel):
    # ``memory_id`` is an internal database id; the UI must not display it as a
    # vector id. It is only used as a React key / lookup handle.
    memory_id: int
    content: str
    memory_type: str
    confidence: float
    importance: float = 0.5
    status: str = "active"
    source_timestamp: Optional[str] = None


class ChatDebugOut(BaseModel):
    retrieved: Sequence[RetrievedMemoryOut] = []
    context_chars: int = 0
    context_sample: str = ""


class ChatPreviewResponse(BaseModel):
    """Read-only result of a chat turn (evaluation/probing).

    Produced without persisting any message, memory, profile or embedding.
    """

    person_id: int
    person_name: str
    reply: str
    confidence: ConfidenceOut
    memory_indicator: Optional[str] = None
    show_memory_sources: bool = False
    sources: Sequence[MemorySourceOut] = []
    retrieved: Sequence[RetrievedMemoryOut] = []
    context_chars: int = 0
    read_only: bool = True


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    confidence: ConfidenceOut
    memory_indicator: Optional[str] = None
    show_memory_sources: bool = False
    sources: Sequence[MemorySourceOut] = []
    learned: Sequence[LearnedMemoryOut] = []
    memory_mode: str = "auto"
    pending_memory: Optional[PendingMemoryOut] = None
    debug: Optional[ChatDebugOut] = None