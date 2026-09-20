"""Retrieval service.

Pipeline for a question:
  1. embed the question
  2. search the vector store (optionally filtered by person)
  3. drop low-confidence and low-similarity candidates
  4. rank by similarity x recency x importance x confidence
  5. de-duplicate memories, keep the best hit per memory
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
class RetrievedMemory:
    memory: Memory
    similarity: float
    score: float
    rank: int = 0
    matched_documents: Sequence[str] = field(default_factory=list)


class RetrievalService:
    def __init__(
        self,
        embedding: EmbeddingService,
        vector_store: VectorStore,
        *,
        min_confidence: float = 0.5,
        default_limit: int = 12,
        min_similarity: float = _MIN_SIMILARITY,
    ) -> None:
        self.embedding = embedding
        self.vector_store = vector_store
        self.min_confidence = min_confidence
        self.default_limit = default_limit
        self.min_similarity = min_similarity
        # Hash embeddings have no semantics; when the provider is offline we
        # re-rank candidates with lexical similarity instead of trusting cosine.
        self.offline = bool(getattr(getattr(embedding, "provider", None), "offline", False))

    def retrieve(
        self,
        session: Session,
        question: str,
        person_id: Optional[int] = None,
        project_id: Optional[int] = None,
        memory_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[RetrievedMemory]:
        limit = limit or self.default_limit
        if not question.strip():
            return []

        # Fail loudly when the stored vectors were produced by a different
        # embedding model/dimension instead of silently searching with
        # incompatible vectors (see EmbeddingService.check_embedding_compatible).
        self.embedding.check_embedding_compatible(session)

        query_embedding = self.embedding.embed_texts([question])[0]

        # Ask for more candidates than we need so low-quality ones can be cut.
        # Offline mode re-ranks lexically, so consider the whole person's memory.
        candidate_count = max(limit * 3, 20)
        if self.offline:
            candidate_count = max(limit * 20, 200)
        where = {"person_id": str(person_id)} if person_id is not None else None
        hits = self.vector_store.query(query_embedding, n_results=candidate_count, where=where)

        # Hybrid fallback: when no vectors exist yet (fresh project, or the
        # vector layer has not been built) rely on lexical search so retrieval
        # still works until embeddings are ready.
        if not hits:
            return self._lexical_retrieve(
                session, question, person_id=person_id, project_id=project_id,
                memory_type=memory_type, limit=limit,
            )

        memories_repo = MemoryRepository(session)
        memory_ids = [h.memory_id for h in hits if h.memory_id]
        memories = {m.id: m for m in memories_repo.get_by_ids(memory_ids)}
        now = datetime.now(timezone.utc)

        candidates: dict[int, RetrievedMemory] = {}
        for hit in hits:
            memory = memories.get(hit.memory_id)
            if memory is None or memory.status != "active":
                continue
            if project_id is not None and memory.project_id != project_id:
                continue  # strict project isolation
            if memory_type is not None and memory.memory_type != memory_type:
                continue
            if memory.confidence < self.min_confidence:
                continue  # low-confidence memories are not presented as fact

            similarity = hit.similarity
            if self.offline:
                document = hit.document or memory.content
                similarity = best_relevance(question, document)
            if similarity < self.min_similarity:
                continue  # irrelevant to the question -> low quality

            age_days = max(0.0, (now - (memory.created_at.replace(tzinfo=timezone.utc) if memory.created_at.tzinfo is None else memory.created_at)).total_seconds() / 86400.0)
            recency = math.exp(-age_days / _RECENCY_HALF_LIFE_DAYS)
            importance_norm = 0.5 + (memory.importance or 0.5) / 2.0
            confidence_norm = 0.5 + (memory.confidence or 0.5) / 2.0
            score = similarity * recency * importance_norm * confidence_norm

            existing = candidates.get(memory.id)
            if existing is None or score > existing.score:
                candidates[memory.id] = RetrievedMemory(
                    memory=memory,
                    similarity=similarity,
                    score=score,
                    matched_documents=[hit.document],
                )

        ranked = sorted(candidates.values(), key=lambda r: r.score, reverse=True)[:limit]
        for index, item in enumerate(ranked):
            item.rank = index + 1
        logger.info("Retrieved %d memories for question (person=%s)", len(ranked), person_id)
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
    ) -> list[RetrievedMemory]:
        """Lexical-only retrieval used when the vector layer has no data.

        Candidates are prefetched with a database token search (OR of LIKE
        patterns) and then ranked with the same multi-signal score as vectors:
        relevance x recency x importance x confidence.
        """
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
        if tokens:
            query = query.where(or_(*(Memory.content.ilike(f"%{t}%") for t in tokens)))
        else:
            query = query.where(Memory.confidence >= self.min_confidence)
        memories = session.scalars(query.order_by(Memory.updated_at.desc()).limit(max(limit * 10, 100))).all()

        now = datetime.now(timezone.utc)
        scored: list[RetrievedMemory] = []
        for memory in memories:
            similarity = best_relevance(question, memory.content or "")
            if similarity < self.min_similarity:
                continue
            if memory.confidence < self.min_confidence:
                continue
            age_days = max(0.0, (now - (memory.created_at.replace(tzinfo=timezone.utc) if memory.created_at.tzinfo is None else memory.created_at)).total_seconds() / 86400.0)
            recency = math.exp(-age_days / _RECENCY_HALF_LIFE_DAYS)
            importance_norm = 0.5 + (memory.importance or 0.5) / 2.0
            confidence_norm = 0.5 + (memory.confidence or 0.5) / 2.0
            score = similarity * recency * importance_norm * confidence_norm
            scored.append(
                RetrievedMemory(
                    memory=memory,
                    similarity=similarity,
                    score=score,
                    matched_documents=[memory.content or ""],
                )
            )
        ranked = sorted(scored, key=lambda r: r.score, reverse=True)[:limit]
        for index, item in enumerate(ranked):
            item.rank = index + 1
        if ranked:
            logger.info("Lexical retrieval fallback found %d memories (person=%s)", len(ranked), person_id)
        return ranked