"""Confidence service.

Converts retrieval output into a usable confidence level using multiple
signals:
  - retrieval similarity (best + mean)
  - number of supporting memories
  - average memory confidence
  - memory recency

Returned levels: HIGH | MEDIUM | LOW.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.schemas.memory import ConfidenceOut
from app.services.retrieval_service import RetrievedMemory

_SUPPORT_SIMILARITY = 0.35


def interpret(retrieved: Sequence[RetrievedMemory]) -> ConfidenceOut:
    if not retrieved:
        return ConfidenceOut(level="LOW", score=0.1, signals={"reason": "no_memories_retrieved"})

    now = datetime.now(timezone.utc)
    similarities = [r.similarity for r in retrieved]
    best_sim = max(similarities)
    mean_sim = sum(similarities) / len(similarities)

    supports = sum(1 for s in similarities if s >= _SUPPORT_SIMILARITY)
    avg_confidence = sum(getattr(r.memory, "confidence", 0.5) for r in retrieved) / len(retrieved)
    avg_importance = sum(getattr(r.memory, "importance", 0.5) for r in retrieved) / len(retrieved)

    ages_days = []
    for r in retrieved:
        created = r.memory.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        ages_days.append(max(0.0, (now - created).total_seconds() / 86400.0))
    avg_age_days = sum(ages_days) / len(ages_days)
    recency_norm = 1.0 / (1.0 + avg_age_days / 90.0)

    support_norm = min(1.0, supports / 3.0)
    score = (
        0.35 * best_sim
        + 0.10 * mean_sim
        + 0.15 * support_norm
        + 0.30 * avg_confidence
        + 0.05 * avg_importance
        + 0.05 * recency_norm
    )
    score = round(max(0.0, min(1.0, score)), 3)

    if score >= 0.7:
        level = "HIGH"
    elif score >= 0.42:
        level = "MEDIUM"
    else:
        level = "LOW"

    return ConfidenceOut(
        level=level,
        score=score,
        signals={
            "best_similarity": round(best_sim, 3),
            "mean_similarity": round(mean_sim, 3),
            "supporting_memories": supports,
            "retrieved_count": len(retrieved),
            "avg_memory_confidence": round(avg_confidence, 3),
            "avg_memory_importance": round(avg_importance, 3),
            "avg_age_days": round(avg_age_days, 1),
        },
    )