"""Conversation summarization service.

Generates bounded summaries of conversation content for context window
optimization. Summaries are derived data that never replace original
messages.

V3.3 Phase 3 — Backup, Recovery, Summarization & Memory Relationships.
"""

from __future__ import annotations

import re
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import Conversation, ConversationSummary, Message, utcnow
from app.database.repositories import ConversationSummaryRepository

logger = get_logger("summarization")

# Configurable threshold: update summary every N new messages since last summary
DEFAULT_UPDATE_THRESHOLD = 20
MAX_CHUNK_MESSAGES = 50


def _sanitize_content(text: str) -> str:
    """Strip potential prompt injection patterns from conversation content.

    Conversation content is untrusted data. We remove lines that look like
    system instructions before sending content to the model for summarization.
    """
    lines = text.split("\n")
    safe_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that look like system instructions
        if stripped.lower().startswith(("you are", "system:", "assistant:", "ignore ", "disregard ")):
            continue
        if stripped.lower().startswith(("please ", "do not ", "don't ", "must ", "should ")):
            # Only skip if it looks like an instruction, not natural conversation
            if any(kw in stripped.lower() for kw in ["ignore", "disregard", "override", "system", "prompt"]):
                continue
        safe_lines.append(line)
    return "\n".join(safe_lines)


class SummarizationService:
    """Generate and manage bounded conversation summaries.

    Summaries use a rolling strategy: when the number of new messages
    since the last summary exceeds a threshold, the summary is updated.
    """

    def __init__(
        self,
        session: Session,
        *,
        update_threshold: int = DEFAULT_UPDATE_THRESHOLD,
    ) -> None:
        self.session = session
        self.repo = ConversationSummaryRepository(session)
        self.update_threshold = update_threshold

    def get_summary(self, conversation_id: int) -> Optional[ConversationSummary]:
        """Get the latest summary for a conversation."""
        return self.repo.get_for_conversation(conversation_id)

    def needs_update(self, conversation_id: int) -> bool:
        """Check if a conversation has enough new messages for a summary update."""
        existing = self.repo.get_for_conversation(conversation_id)
        if existing is None:
            # No summary yet — check if there are enough messages
            msg_count = self.session.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
            ) or 0
            return msg_count >= self.update_threshold

        # Count messages since last summary
        new_count = self.session.scalar(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation_id,
                Message.id > (existing.message_end_id or 0),
            )
        ) or 0
        return new_count >= self.update_threshold

    def generate_summary(
        self,
        conversation_id: int,
        *,
        project_id: Optional[int] = None,
        model: str = "",
    ) -> Optional[ConversationSummary]:
        """Generate a summary of a conversation using bounded chunks.

        For short conversations (< MAX_CHUNK_MESSAGES), summarize directly.
        For long conversations, use a rolling summary strategy.
        """
        messages = list(self.session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc().nullslast(), Message.id.asc())
        ).all())

        if not messages:
            return None

        # Sanitize all message content
        chunks = []
        for msg in messages:
            safe_content = _sanitize_content(msg.content or "")
            if safe_content.strip():
                sender = msg.sender or "Unknown"
                chunks.append(f"{sender}: {safe_content}")

        if not chunks:
            return None

        # Build summary text from message chunks
        if len(chunks) <= MAX_CHUNK_MESSAGES:
            summary_text = self._summarize_chunk(chunks)
        else:
            # Rolling summary: summarize in chunks, then combine
            summary_text = self._rolling_summary(chunks)

        # Get message range
        first_msg = messages[0]
        last_msg = messages[-1]

        return self.repo.upsert(
            conversation_id,
            summary=summary_text,
            project_id=project_id or (first_msg.conversation_id and self._get_project_id(conversation_id)),
            message_start_id=first_msg.id,
            message_end_id=last_msg.id,
            message_count=len(messages),
            model=model or "heuristic",
        )

    def _summarize_chunk(self, chunks: list[str]) -> str:
        """Summarize a bounded chunk of messages using heuristic extraction.

        Extracts key topics, decisions, and facts without requiring an AI
        provider. This is a deterministic, offline fallback.
        """
        topics: list[str] = []
        decisions: list[str] = []
        facts: list[str] = []

        for chunk in chunks:
            lower = chunk.lower()
            # Extract topic indicators
            if any(kw in lower for kw in ["about", "topic", "regarding", "discuss"]):
                topics.append(chunk)
            # Extract decision indicators
            if any(kw in lower for kw in ["decided", "agree", "plan", "will do", "let's"]):
                decisions.append(chunk)
            # Extract fact indicators
            if any(kw in lower for kw in ["is a", "are the", "was born", "lives in", "works at", "likes", "prefers"]):
                facts.append(chunk)

        parts = []
        if facts:
            parts.append("Key facts: " + "; ".join(facts[:10]))
        if decisions:
            parts.append("Decisions: " + "; ".join(decisions[:5]))
        if topics:
            parts.append("Topics discussed: " + "; ".join(topics[:5]))

        if not parts:
            # Fallback: first and last few messages
            all_text = [c.split(": ", 1)[-1] if ": " in c else c for c in chunks]
            parts = [f"Conversation between {chunks[0].split(': ')[0] if ': ' in chunks[0] else 'participants'}"]
            if len(all_text) > 2:
                parts.append(f"Started with: {all_text[0][:100]}")
                parts.append(f"Ended with: {all_text[-1][:100]}")
            parts.append(f"{len(chunks)} messages exchanged")

        return ". ".join(parts)

    def _rolling_summary(self, chunks: list[str]) -> str:
        """Summarize long conversations using chunked rolling strategy."""
        summaries = []
        for i in range(0, len(chunks), MAX_CHUNK_MESSAGES):
            chunk = chunks[i:i + MAX_CHUNK_MESSAGES]
            summaries.append(self._summarize_chunk(chunk))

        # Combine sub-summaries
        if len(summaries) == 1:
            return summaries[0]

        combined = []
        combined.append(f"Conversation spanning {len(chunks)} messages.")
        for i, s in enumerate(summaries):
            combined.append(f"Part {i+1}: {s}")
        return " ".join(combined)

    def _get_project_id(self, conversation_id: int) -> Optional[int]:
        conv = self.session.get(Conversation, conversation_id)
        return conv.project_id if conv else None

    def delete_summary(self, conversation_id: int) -> int:
        return self.repo.delete_for_conversation(conversation_id)
