"""Memory disclosure helpers.

Small, honest indications the user can see ("Based on an earlier
conversation..."). Never exposes internal vector ids. When
SHOW_MEMORY_SOURCES is on, the actual influencing memories are returned so the
UI can render them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from app.schemas.chat import MemorySourceOut
from app.services.retrieval_service import RetrievedMemory

_INDICATOR_MIN_SIMILARITY = 0.28


def build_indicator(retrieved: Sequence[RetrievedMemory]) -> Optional[str]:
    """Return a short human-readable disclosure when memories helped."""
    if not retrieved:
        return None
    best = max(r.similarity for r in retrieved)
    if best < _INDICATOR_MIN_SIMILARITY:
        return None
    return "Based on an earlier conversation with this person..."


def build_sources(retrieved: Sequence[RetrievedMemory], limit: int = 5) -> list[MemorySourceOut]:
    """Sources exposed to the user when SHOW_MEMORY_SOURCES=true."""
    sources: list[MemorySourceOut] = []
    for item in sorted(retrieved, key=lambda r: r.similarity, reverse=True)[:limit]:
        memory = item.memory
        source_timestamp = None
        if memory.created_at:
            ts = memory.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.now().astimezone().tzinfo)
            source_timestamp = ts.isoformat()
        sources.append(
            MemorySourceOut(
                memory_id=memory.id,
                content=memory.content[:200],
                memory_type=memory.memory_type,
                confidence=memory.confidence,
                importance=memory.importance,
                status=memory.status,
                source_timestamp=source_timestamp,
            )
        )
    return sources