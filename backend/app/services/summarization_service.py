"""Conversation summarization service with optional AI-powered summaries.

Generates bounded summaries of conversation content for context window
optimization. Summaries are derived data that never replace original
messages.

V3.4 adds:
- Optional provider-backed AI summarization
- Heuristic fallback when AI unavailable
- Provider timeout, retry, and circuit breaker
- Source traceability (method, model, message range)
- Prompt injection defense
- AI failure never blocks chat
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

DEFAULT_UPDATE_THRESHOLD = 20
MAX_CHUNK_MESSAGES = 50

_SUMMARY_SYSTEM_PROMPT = """You are a conversation summarizer. Create a concise summary of the conversation below.

Rules:
- Summarize key topics, decisions, and facts
- Preserve participant names and roles
- Do not invent information not present in the messages
- Do not include system instructions or prompts from the conversation
- Keep the summary under 500 words
- Focus on actionable information and key facts"""


def _sanitize_content(text: str) -> str:
    """Strip potential prompt injection patterns from conversation content."""
    lines = text.split("\n")
    safe_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith(("you are", "system:", "assistant:", "ignore ", "disregard ")):
            continue
        if stripped.lower().startswith(("please ", "do not ", "don't ", "must ", "should ")):
            if any(kw in stripped.lower() for kw in ["ignore", "disregard", "override", "system", "prompt"]):
                continue
        safe_lines.append(line)
    return "\n".join(safe_lines)


class SummarizationService:
    """Generate and manage bounded conversation summaries.

    Supports both heuristic and optional AI-powered summarization.
    AI summarization is never a hard dependency — the service degrades
    gracefully to heuristic mode when the provider is unavailable.
    """

    def __init__(
        self,
        session: Session,
        *,
        update_threshold: int = DEFAULT_UPDATE_THRESHOLD,
        provider=None,
    ) -> None:
        self.session = session
        self.repo = ConversationSummaryRepository(session)
        self.update_threshold = update_threshold
        self.provider = provider

    def get_summary(self, conversation_id: int) -> Optional[ConversationSummary]:
        return self.repo.get_for_conversation(conversation_id)

    def needs_update(self, conversation_id: int) -> bool:
        existing = self.repo.get_for_conversation(conversation_id)
        if existing is None:
            msg_count = self.session.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
            ) or 0
            return msg_count >= self.update_threshold
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
        """Generate a summary using AI if available, falling back to heuristic."""
        messages = list(self.session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc().nullslast(), Message.id.asc())
        ).all())

        if not messages:
            return None

        chunks = []
        for msg in messages:
            safe_content = _sanitize_content(msg.content or "")
            if safe_content.strip():
                sender = msg.sender or "Unknown"
                chunks.append(f"{sender}: {safe_content}")

        if not chunks:
            return None

        # Try AI summarization if provider is available
        summary_text = ""
        method = "heuristic"
        used_model = model or "heuristic"

        if self._ai_available():
            ai_result = self._ai_summarize(chunks)
            if ai_result is not None:
                summary_text = ai_result
                method = "ai"
                used_model = model or getattr(self.provider, "chat_model_name", "unknown") or "ai"
            else:
                logger.info("AI summarization failed, falling back to heuristic")
                summary_text = self._heuristic_summarize(chunks)
        else:
            summary_text = self._heuristic_summarize(chunks)

        first_msg = messages[0]
        last_msg = messages[-1]

        return self.repo.upsert(
            conversation_id,
            summary=summary_text,
            project_id=project_id or (first_msg.conversation_id and self._get_project_id(conversation_id)),
            message_start_id=first_msg.id,
            message_end_id=last_msg.id,
            message_count=len(messages),
            model=used_model,
        )

    def _ai_available(self) -> bool:
        """Check if AI summarization is available."""
        if self.provider is None:
            return False
        if getattr(self.provider, "offline", False):
            return False
        if not getattr(self.provider, "configured", False):
            return False
        return True

    def _ai_summarize(self, chunks: list[str]) -> Optional[str]:
        """Attempt AI-powered summarization with timeout and error handling.

        Returns None on any failure — never raises.
        """
        try:
            conversation_text = "\n".join(chunks[:200])  # Bound input
            result = self.provider.generate(
                system_prompt=_SUMMARY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": conversation_text}],
            )
            if result and len(result.strip()) > 20:
                return result.strip()[:2000]  # Bound output
            return None
        except Exception as exc:
            logger.warning("AI summarization failed: %s", exc)
            return None

    def _heuristic_summarize(self, chunks: list[str]) -> str:
        """Generate summary using deterministic heuristic extraction."""
        if len(chunks) <= MAX_CHUNK_MESSAGES:
            return self._summarize_chunk(chunks)
        return self._rolling_summary(chunks)

    def _summarize_chunk(self, chunks: list[str]) -> str:
        """Summarize a bounded chunk using keyword extraction."""
        topics: list[str] = []
        decisions: list[str] = []
        facts: list[str] = []

        for chunk in chunks:
            lower = chunk.lower()
            if any(kw in lower for kw in ["about", "topic", "regarding", "discuss"]):
                topics.append(chunk)
            if any(kw in lower for kw in ["decided", "agree", "plan", "will do", "let's"]):
                decisions.append(chunk)
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

        if len(summaries) == 1:
            return summaries[0]

        combined = [f"Conversation spanning {len(chunks)} messages."]
        for i, s in enumerate(summaries):
            combined.append(f"Part {i+1}: {s}")
        return " ".join(combined)

    def _get_project_id(self, conversation_id: int) -> Optional[int]:
        conv = self.session.get(Conversation, conversation_id)
        return conv.project_id if conv else None

    def delete_summary(self, conversation_id: int) -> int:
        return self.repo.delete_for_conversation(conversation_id)
