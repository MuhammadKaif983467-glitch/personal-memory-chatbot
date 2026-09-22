"""Retrieval service with configurable ranking pipeline.

Pipeline for a question:
  1. embed the question
  2. search the vector store (optionally filtered by person)
  3. security filtering (project isolation, confidence threshold)
  4. conversation filtering (date range, conversation context)
  5. scoring with configurable weights
  6. deduplication
  7. ranking
  8. context budget truncation

V3.4 adds:
  - configurable ranking weights (documented, no magic numbers)
  - retrieval explanations for debugging
  - conversation-aware context boost
  - date range filtering
  - same-person boost
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import Memory
from app.database.repositories import MemoryRepository
from app.services.embedding_service import EmbeddingService
from app.utils.similarity import best_relevance
from app.vectorstore.base import VectorStore

logger = get_logger("retrieval")

_RECENCY_HALF_LIFE_DAYS = 90.0
_MIN_SIMILARITY = 0.18


@dataclass
class RankingWeights:
    """Configurable ranking weights for the retrieval scoring pipeline.

    Each weight controls the contribution of a signal to the final score.
    The final score is computed as:
        similarity^w_similarity * recency^w_recency * importance^w_importance
        * confidence^w_confidence * context_boost

    Default weights are tuned for a personal memory assistant where
    semantic similarity and confidence matter most.
    """
    similarity: float = 1.0
    recency: float = 1.0
    importance: float = 0.5
    confidence: float = 0.5
    conversation_boost: float = 1.3
    same_person_boost: float = 1.1


@dataclass
class RetrievalExplanation:
    """Explains why a memory was selected and how it was scored.

    Used for debugging retrieval decisions. Not exposed to end users
    unless debug_retrieval is enabled.
    """
    similarity: float = 0.0
    recency: float = 0.0
    importance_raw: float = 0.0
    confidence_raw: float = 0.0
    context_reason: str = ""
    base_score: float = 0.0
    final_score: float = 0.0
    source: str = "vector"  # "vector" | "lexical"


@dataclass
class RetrievedMemory:
    memory: Memory
    similarity: float
    score: float
    rank: int = 0
    matched_documents: Sequence[str] = field(default_factory=list)
    context_reason: str = ""
    explanation: Optional[RetrievalExplanation] = None


class RetrievalService:
    def __init__(
        self,
        embedding: EmbeddingService,
        vector_store: VectorStore,
        *,
        min_confidence: float = 0.5,
        default_limit: int = 12,
        min_similarity: float = _MIN_SIMILARITY,
        weights: Optional[RankingWeights] = None,
    ) -> None:
        self.embedding = embedding
        self.vector_store = vector_store
        self.min_confidence = min_confidence
        self.default_limit = default_limit
        self.min_similarity = min_similarity
        self.weights = weights or RankingWeights()
        self.offline = bool(getattr(getattr(embedding, "provider", None), "offline", False))

    def _score(
        self,
        similarity: float,
        created_at: datetime,
        importance: float,
        confidence: float,
        context_reason: str = "",
    ) -> tuple[float, RetrievalExplanation]:
        """Compute retrieval score with configurable weights and return explanation."""
        now = datetime.now(timezone.utc)
        age_days = max(0.0, (now - (created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at)).total_seconds() / 86400.0)
        recency = math.exp(-age_days / _RECENCY_HALF_LIFE_DAYS)

        w = self.weights
        base_score = (
            math.pow(similarity, w.similarity)
            * math.pow(recency, w.recency)
            * math.pow(0.5 + importance / 2.0, w.importance)
            * math.pow(0.5 + confidence / 2.0, w.confidence)
        )

        context_boost = 1.0
        if context_reason == "current_conversation":
            context_boost = w.conversation_boost
        elif context_reason == "same_person":
            context_boost = w.same_person_boost

        final_score = base_score * context_boost

        explanation = RetrievalExplanation(
            similarity=similarity,
            recency=recency,
            importance_raw=importance,
            confidence_raw=confidence,
            context_reason=context_reason,
            base_score=base_score,
            final_score=final_score,
        )
        return final_score, explanation

    def retrieve(
        self,
        session: Session,
        question: str,
        person_id: Optional[int] = None,
        project_id: Optional[int] = None,
        memory_type: Optional[str] = None,
        limit: Optional[int] = None,
        *,
        conversation_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[RetrievedMemory]:
        limit = limit or self.default_limit
        if not question.strip():
            return []

        self.embedding.check_embedding_compatible(session)

        query_embedding = self.embedding.embed_texts([question])[0]

        candidate_count = max(limit * 3, 20)
        if self.offline:
            candidate_count = max(limit * 20, 200)
        where = {"person_id": str(person_id)} if person_id is not None else None
        hits = self.vector_store.query(query_embedding, n_results=candidate_count, where=where)

        if not hits:
            return self._lexical_retrieve(
                session, question, person_id=person_id, project_id=project_id,
                memory_type=memory_type, limit=limit, conversation_id=conversation_id,
                date_from=date_from, date_to=date_to,
            )

        memories_repo = MemoryRepository(session)
        memory_ids = [h.memory_id for h in hits if h.memory_id]
        memories = {m.id: m for m in memories_repo.get_by_ids(memory_ids)}

        # Conversation context: find memories sourced from messages in this conversation
        conversation_memories = set()
        if conversation_id is not None:
            from app.database.models import Message
            conv_message_ids = set(
                session.scalars(
                    select(Message.id).where(Message.conversation_id == conversation_id)
                ).all()
            )
            conversation_memories = {
                mem.id for mem in session.scalars(
                    select(Memory).where(
                        Memory.source_message_id.isnot(None),
                        Memory.status == "active",
                    )
                ).all()
                if mem.source_message_id in conv_message_ids
            }

        candidates: dict[int, RetrievedMemory] = {}
        for hit in hits:
            memory = memories.get(hit.memory_id)
            if memory is None or memory.status != "active":
                continue
            # Security: project isolation
            if project_id is not None and memory.project_id != project_id:
                continue
            if memory_type is not None and memory.memory_type != memory_type:
                continue
            # Security: confidence threshold
            if memory.confidence < self.min_confidence:
                continue
            # Temporal filtering
            if date_from is not None and memory.created_at is not None:
                mem_dt = memory.created_at.replace(tzinfo=timezone.utc) if memory.created_at.tzinfo is None else memory.created_at
                if mem_dt < date_from:
                    continue
            if date_to is not None and memory.created_at is not None:
                mem_dt = memory.created_at.replace(tzinfo=timezone.utc) if memory.created_at.tzinfo is None else memory.created_at
                if mem_dt > date_to:
                    continue

            similarity = hit.similarity
            if self.offline:
                document = hit.document or memory.content
                similarity = best_relevance(question, document)
            if similarity < self.min_similarity:
                continue

            # Determine context reason
            ctx_reason = ""
            if conversation_id is not None and memory.id in conversation_memories:
                ctx_reason = "current_conversation"
            elif person_id is not None and memory.person_id == person_id:
                ctx_reason = "same_person"

            score, explanation = self._score(
                similarity, memory.created_at, memory.importance or 0.5,
                memory.confidence or 0.5, ctx_reason,
            )
            explanation.source = "vector"

            existing = candidates.get(memory.id)
            if existing is None or score > existing.score:
                candidates[memory.id] = RetrievedMemory(
                    memory=memory,
                    similarity=similarity,
                    score=score,
                    matched_documents=[hit.document],
                    context_reason=ctx_reason,
                    explanation=explanation,
                )

        ranked = sorted(candidates.values(), key=lambda r: r.score, reverse=True)[:limit]
        for index, item in enumerate(ranked):
            item.rank = index + 1
        logger.info("Retrieved %d memories (person=%s, conv=%s)", len(ranked), person_id, conversation_id)
        return ranked

    def _lexical_retrieve(
        self,
        session: Session,
        question: str,
        *,
        person_id: Optional[int],
        project_id: Optional[int],
        memory_type: Optional[str],
        limit: int,
        conversation_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[RetrievedMemory]:
        """Lexical-only retrieval used when the vector layer has no data."""
        import re as _re

        from sqlalchemy import or_

        tokens = [t for t in _re.split(r"\W+", question.lower()) if len(t) >= 3][:8]

        query = select(Memory).where(Memory.status == "active")
        if person_id is not None:
            query = query.where(Memory.person_id == person_id)
        if project_id is not None:
            query = query.where(Memory.project_id == project_id)
        if memory_type is not None:
            query = query.where(Memory.memory_type == memory_type)
        if date_from is not None:
            query = query.where(Memory.created_at >= date_from)
        if date_to is not None:
            query = query.where(Memory.created_at <= date_to)
        if tokens:
            query = query.where(or_(*(Memory.content.ilike(f"%{t}%") for t in tokens)))
        else:
            query = query.where(Memory.confidence >= self.min_confidence)
        memories = session.scalars(query.order_by(Memory.updated_at.desc()).limit(max(limit * 10, 100))).all()

        # Conversation context boost for lexical retrieval
        conversation_memories = set()
        if conversation_id is not None:
            from app.database.models import Message
            conv_message_ids = set(
                session.scalars(
                    select(Message.id).where(Message.conversation_id == conversation_id)
                ).all()
            )
            conversation_memories = {
                mem.id for mem in memories
                if mem.source_message_id is not None and mem.source_message_id in conv_message_ids
            }

        scored: list[RetrievedMemory] = []
        for memory in memories:
            similarity = best_relevance(question, memory.content or "")
            if similarity < self.min_similarity:
                continue
            if memory.confidence < self.min_confidence:
                continue

            ctx_reason = ""
            if conversation_id is not None and memory.id in conversation_memories:
                ctx_reason = "current_conversation"
            elif person_id is not None and memory.person_id == person_id:
                ctx_reason = "same_person"

            score, explanation = self._score(
                similarity, memory.created_at, memory.importance or 0.5,
                memory.confidence or 0.5, ctx_reason,
            )
            explanation.source = "lexical"

            scored.append(
                RetrievedMemory(
                    memory=memory,
                    similarity=similarity,
                    score=score,
                    matched_documents=[memory.content or ""],
                    context_reason=ctx_reason,
                    explanation=explanation,
                )
            )
        ranked = sorted(scored, key=lambda r: r.score, reverse=True)[:limit]
        for index, item in enumerate(ranked):
            item.rank = index + 1
        if ranked:
            logger.info("Lexical retrieval found %d memories (person=%s, conv=%s)", len(ranked), person_id, conversation_id)
        return ranked
