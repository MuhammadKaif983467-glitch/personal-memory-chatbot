"""Memory retrieval context for prompts.

Extracts memory formatting from context_service._memories into a standalone
pipeline service for reuse across chat and preview flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.services.retrieval_service import RetrievedMemory


@dataclass
class MemoryContext:
    """Structured output of memory context extraction.

    Attributes
    ----------
    memories_text:
        Formatted multi-line string of retrieved memories.
    memory_count:
        Number of memories included in the text.
    best_similarity:
        Highest similarity score among the retrieved set.
    """

    memories_text: str
    memory_count: int
    best_similarity: float


def build_memory_context(
    retrieved: Sequence[RetrievedMemory],
    limit: int = 10,
    max_snippet_chars: int = 400,
) -> MemoryContext:
    """Format retrieved memories into prompt-ready context.

    Parameters
    ----------
    retrieved:
        Ranked list of RetrievedMemory objects from the retrieval service.
    limit:
        Maximum number of memories to include.
    max_snippet_chars:
        Truncate each memory content to this many characters.

    Returns
    -------
    MemoryContext
        Structured context ready for prompt assembly.
    """
    if not retrieved:
        return MemoryContext(
            memories_text="(no relevant memories retrieved)",
            memory_count=0,
            best_similarity=0.0,
        )

    best_sim = max(r.similarity for r in retrieved)
    sorted_retrieved = sorted(retrieved, key=lambda r: r.similarity, reverse=True)

    lines: list[str] = []
    for index, item in enumerate(sorted_retrieved[:limit], start=1):
        memory = item.memory
        snippet = (getattr(memory, "content", None) or "").replace("\n", " ")
        if len(snippet) > max_snippet_chars:
            snippet = snippet[:max_snippet_chars].rstrip() + "..."
        created = memory.created_at.date().isoformat() if memory.created_at else "?"
        mem_type = getattr(memory, "memory_type", "unknown")
        confidence = getattr(memory, "confidence", 0.0)
        lines.append(
            f"{index}. [{item.similarity:.2f}] ({mem_type}, conf {confidence:.2f}) "
            f"{snippet} — recalled from {created}"
        )

    return MemoryContext(
        memories_text="\n".join(lines),
        memory_count=len(lines),
        best_similarity=best_sim,
    )
