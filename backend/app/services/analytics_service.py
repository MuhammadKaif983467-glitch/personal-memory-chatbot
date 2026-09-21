"""Read-only analytics: unified search + conversation analysis.

Both features are deterministic and offline (no AI provider involved), so they
work in every provider state and are testable without credentials.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.models import Conversation, Message
from app.database.repositories import (
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
    PersonRepository,
)
from app.schemas.analytics import (
    ConversationAnalysisOut,
    ParticipantCount,
    SearchConversationHit,
    SearchMemoryHit,
    SearchMessageHit,
    SearchResponse,
    TopicHit,
)

_STOPWORDS = {
    "the", "and", "for", "are", "you", "your", "i", "my", "me", "to", "of",
    "a", "in", "that", "this", "it", "is", "was", "on", "at", "with", "have",
    "has", "had", "what", "when", "where", "who", "how", "why", "not", "no",
    "but", "so", "if", "we", "our", "us", "they", "them", "their", "he", "she",
    "his", "her", "itself", "s", "t", "ok", "okay", "yeah", "yes", "oh", "ha",
    "haha", "hmm", "um", "like", "just", "really", "think", "know", "want",
    "going", "get", "got", "say", "said", "can", "will", "would", "could",
    "should", "do", "did", "does", "also", "there", "then", "than", "from",
    "by", "or", "as", "am", "be", "been", "being", "now", "here", "all", "any",
}

# Deterministic evidence cues.
_DECISION_RE = re.compile(r"\b(decided|decision|we agreed|settled on|finali[sz]ed|finalized|finalised)\b", re.I)
_PLAN_RE = re.compile(r"\b(plan(?:ning)?|will\s+buy|going to|next week|tomorrow|gonna|we'll)\b", re.I)
_COMMITMENT_RE = re.compile(r"\b(i'?ll|promise|remind me|deadline|due on|by monday|by friday|will send|will call)\b", re.I)


def _tokens(text: str) -> Sequence[str]:
    cleaned = re.sub(r"[^\w\s]", " ", text.casefold())
    return [t for t in cleaned.split() if t not in _STOPWORDS]


def _truncate(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


class AnalyticsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- unified search ----

    def search(
        self,
        *,
        query: str = "",
        project_id: Optional[int] = None,
        person_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        date_from=None,
        date_to=None,
        memory_type: Optional[str] = None,
        status: str = "active",
        limit: int = 20,
    ) -> SearchResponse:
        messages = self._search_messages(
            query, project_id=project_id, person_id=person_id,
            conversation_id=conversation_id, date_from=date_from, date_to=date_to, limit=limit,
        )
        memories = self._search_memories(
            query, project_id=project_id, person_id=person_id,
            conversation_id=conversation_id, memory_type=memory_type, status=status, limit=limit,
        )
        conversations = self._search_conversations(
            query, project_id=project_id, message_hits=messages, limit=limit,
        )
        return SearchResponse(
            query=query,
            messages=messages,
            memories=memories,
            conversations=conversations,
            total=len(messages) + len(memories) + len(conversations),
        )

    def _search_messages(
        self, query: str, *, project_id, person_id, conversation_id, date_from, date_to, limit: int,
    ) -> Sequence[SearchMessageHit]:
        tokens = [t for t in _tokens(query) if len(t) >= 2][:8]

        # Try FTS5 first, fall back to LIKE-based search
        msg_repo = MessageRepository(self.session)
        if tokens:
            fts_results = msg_repo.fts_search(
                " ".join(tokens),
                project_id=project_id,
                person_id=person_id,
                conversation_id=conversation_id,
                limit=limit,
            )
            if fts_results is not None and len(fts_results) > 0:
                titles = {
                    conv.id: conv.title
                    for conv in ConversationRepository(self.session).list_all(project_id=project_id)
                }
                hits: list[SearchMessageHit] = []
                for message in fts_results:
                    hits.append(
                        SearchMessageHit(
                            message_id=message.id,
                            conversation_id=message.conversation_id,
                            conversation_title=titles.get(message.conversation_id, ""),
                            sender=message.sender,
                            content=_truncate(message.content or ""),
                            timestamp=message.timestamp,
                        )
                    )
                return hits

        # Fallback: LIKE-based search (original implementation)
        q = select(Message).join(Conversation, Conversation.id == Message.conversation_id)
        if tokens:
            q = q.where(
                or_(*(Message.content.ilike(f"%{t}%") for t in tokens))
            )
        if conversation_id is not None:
            q = q.where(Message.conversation_id == conversation_id)
        if person_id is not None:
            q = q.where(Message.person_id == person_id)
        if project_id is not None:
            q = q.where(Conversation.project_id == project_id)
        if date_from is not None:
            q = q.where(Message.timestamp >= date_from)
        if date_to is not None:
            q = q.where(Message.timestamp <= date_to)
        q = q.order_by(Message.timestamp.desc().nullslast(), Message.id.desc()).limit(limit)
        titles = {
            conv.id: conv.title
            for conv in ConversationRepository(self.session).list_all(project_id=project_id)
        }
        hits: list[SearchMessageHit] = []
        for message in self.session.scalars(q).all():
            hits.append(
                SearchMessageHit(
                    message_id=message.id,
                    conversation_id=message.conversation_id,
                    conversation_title=titles.get(message.conversation_id, ""),
                    sender=message.sender,
                    content=_truncate(message.content or ""),
                    timestamp=message.timestamp,
                )
            )
        return hits

    def _search_memories(
        self, query: str, *, project_id, person_id, conversation_id, memory_type, status, limit: int,
    ) -> Sequence[SearchMemoryHit]:
        repo = MemoryRepository(self.session)
        rows = repo.search(
            query_text=query,
            person_id=person_id,
            project_id=project_id,
            memory_type=memory_type,
            status=status,
            limit=limit,
        )
        names = {person.id: person.name for person in PersonRepository(self.session).list_all()}
        hits: list[SearchMemoryHit] = []
        for memory in rows:
            # If conversation_id is provided, ensure the memory's source message
            # belongs to that conversation (skip if source ties to another conversation).
            if conversation_id is not None and memory.source_message_id is not None:
                source = MessageRepository(self.session).get(memory.source_message_id)
                if source is None or source.conversation_id != conversation_id:
                    continue
            hits.append(
                SearchMemoryHit(
                    memory_id=memory.id,
                    person_id=memory.person_id,
                    person_name=names.get(memory.person_id, ""),
                    content=_truncate(memory.content or ""),
                    memory_type=memory.memory_type,
                    confidence=memory.confidence,
                    status=memory.status,
                    created_at=memory.created_at,
                )
            )
        return hits

    def _search_conversations(
        self, query: str, *, project_id, message_hits, limit: int,
    ) -> Sequence[SearchConversationHit]:
        titles = [t for t in _tokens(query) if len(t) >= 2][:4]
        matched_ids = {h.conversation_id for h in message_hits}
        repo = ConversationRepository(self.session)
        hits: list[SearchConversationHit] = []
        for conversation in repo.list_all(project_id=project_id):
            if conversation.id in matched_ids:
                hits.append(
                    SearchConversationHit(
                        conversation_id=conversation.id,
                        title=conversation.title,
                        message_count=repo.message_count(conversation.id),
                    )
                )
                continue
            if titles and all(t not in conversation.title.casefold() for t in titles):
                continue
            if not titles and not matched_ids:
                continue
            hits.append(
                SearchConversationHit(
                    conversation_id=conversation.id,
                    title=conversation.title,
                    message_count=repo.message_count(conversation.id),
                )
            )
        return hits[:limit]

    # ---- conversation analysis ----

    def analyze_conversation(self, conversation_id: int) -> ConversationAnalysisOut:
        conversation = ConversationRepository(self.session).get(conversation_id)
        if conversation is None:
            raise ValueError("conversation not found")
        messages = MessageRepository(self.session).list_by_conversation(conversation_id)

        timestamps = [m.timestamp for m in messages if m.timestamp is not None]
        participants = Counter(
            (m.sender or "unknown").strip() or "unknown" for m in messages
        )

        content_rows = [m for m in messages if m.content and m.content.strip()]

        counts: Counter[str, int] = Counter()
        for message in content_rows:
            for token in set(_tokens(message.content or "")):
                counts[token] += 1
        top = [t for t, _ in counts.most_common(12) if counts[t] >= 2 or len(counts) <= 12]

        def _cue_rows(regex: "re.Pattern") -> Sequence[TopicHit]:
            seen: dict[str, int] = {}
            samples: dict[str, str] = {}
            for message in content_rows:
                if regex.search(message.content):
                    key = _truncate(message.content, 60)
                    seen[key] = seen.get(key, 0) + 1
                    samples.setdefault(key, _truncate(message.content))
            return [TopicHit(value=k, message_count=v, sample=samples[k]) for k, v in seen.items()][:5]

        topics = [TopicHit(value=t, message_count=counts[t], sample="") for t in top]

        return ConversationAnalysisOut(
            conversation_id=conversation_id,
            person_id=conversation.person_id,
            project_id=conversation.project_id,
            source=conversation.source,
            message_count=len(messages),
            date_start=min(timestamps) if timestamps else None,
            date_end=max(timestamps) if timestamps else None,
            participants=[
                ParticipantCount(sender=sender, count=count)
                for sender, count in participants.most_common()
            ],
            top_topics=topics,
            decisions=_cue_rows(_DECISION_RE),
            plans=_cue_rows(_PLAN_RE),
            commitments=_cue_rows(_COMMITMENT_RE),
        )