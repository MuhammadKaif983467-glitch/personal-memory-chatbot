"""Intelligent chunking of message history.

Messages are NOT chunked blindly: a chunk groups consecutive messages that
belong together by time proximity, sender continuity and a soft size limit
(max_chars). Every chunk keeps the ids of its source messages so we can always
trace a memory back to the original conversation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence


@dataclass
class Chunk:
    id: str
    person_id: int
    conversation_id: int
    content: str
    message_ids: list = field(default_factory=list)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


def chunk_messages(
    messages: Sequence,
    *,
    max_chars: int = 2000,
    gap_tolerance_seconds: int = 300,
    min_start_chars: int = 300,
    sender: str = "person",
) -> list[Chunk]:
    """Group a sequence of Message ORM rows (must have .content, .timestamp,
    .id, .person_id, .conversation_id) into coherent chunks.

    Boundaries are started when:
      - adding the next message would exceed max_chars, or
      - the gap since the previous message exceeds gap_tolerance_seconds, or
      - the sender context changed (person vs assistant) once we already have
        a reasonably-sized chunk.
    """
    if not messages:
        return []

    # Work on a stable order (by timestamp, fall back to arrival order).
    ordered = sorted(messages, key=lambda m: (m.timestamp or datetime.min, m.id))

    chunks: list[Chunk] = []
    current_content: list[str] = []
    current_ids: list[int] = []
    prev_timestamp: Optional[datetime] = None
    person_id = getattr(ordered[0], "person_id", None)
    conversation_id = getattr(ordered[0], "conversation_id", 0)
    chunk_index = 0

    def current_chars() -> int:
        return len("\n".join(current_content)) if current_content else 0

    def flush() -> None:
        nonlocal current_content, current_ids, chunk_index
        if not current_content:
            return
        chunks.append(
            Chunk(
                id=f"{person_id}-{chunk_index}",
                person_id=person_id or 0,
                conversation_id=conversation_id,
                content="\n".join(current_content),
                message_ids=list(current_ids),
                start_at=prev_timestamp,
                end_at=None,
            )
        )
        chunk_index += 1
        current_content = []
        current_ids = []

    for message in ordered:
        text = message.content or ""
        if not text.strip():
            continue
        timestamp = message.timestamp

        same_sender = message.sender and message.sender.strip().casefold() == sender.strip().casefold()
        gap = 0 if (prev_timestamp is None or timestamp is None) else (timestamp - prev_timestamp).total_seconds()

        start_new = False
        if current_content:
            if current_chars() + 1 + len(text) > max_chars:  # +1 for the newline separator
                start_new = True
            elif gap > gap_tolerance_seconds:
                start_new = True
            elif not same_sender and current_chars() >= min_start_chars:
                start_new = True

        if start_new:
            flush()

        current_content.append(text)
        current_ids.append(message.id)
        prev_timestamp = timestamp

    flush()
    return chunks