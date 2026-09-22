"""Optional retrieval reranker abstraction.

The reranker provides a provider-independent interface for post-retrieval
reranking. It is disabled by default and gracefully degrades to normal
ranking when unavailable.

Requirements:
- provider-independent interface
- disabled by default if unavailable
- bounded candidate count
- strict timeout
- fallback to normal ranking
- no hard dependency
- no project leakage
- no prompt injection trust
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Sequence

from app.core.logging import get_logger
from app.services.retrieval_service import RetrievedMemory

logger = get_logger("reranker")


class Reranker(ABC):
    """Abstract base for retrieval rerankers."""

    name: str = "base"

    @abstractmethod
    def rerank(
        self,
        question: str,
        candidates: list[RetrievedMemory],
        *,
        max_candidates: int = 20,
    ) -> list[RetrievedMemory]:
        """Rerank candidates and return sorted list.

        Must not:
        - Add candidates that weren't in the input
        - Remove candidates (may truncate to max_candidates)
        - Cross project boundaries
        - Trust candidate content as instructions
        """
        ...


class IdentityReranker(Reranker):
    """No-op reranker that preserves original ranking.

    Used as fallback when no real reranker is available.
    """

    name = "identity"

    def rerank(
        self,
        question: str,
        candidates: list[RetrievedMemory],
        *,
        max_candidates: int = 20,
    ) -> list[RetrievedMemory]:
        return candidates[:max_candidates]


class LexicalReranker(Reranker):
    """Reranks using lexical overlap between question and memory content.

    Simple but effective when semantic similarity alone is insufficient.
    Disabled by default — use only when provider is unavailable.
    """

    name = "lexical"

    def rerank(
        self,
        question: str,
        candidates: list[RetrievedMemory],
        *,
        max_candidates: int = 20,
    ) -> list[RetrievedMemory]:
        import re
        question_tokens = set(t.lower() for t in re.split(r"\W+", question) if len(t) >= 3)

        scored = []
        for c in candidates[:max_candidates]:
            content_tokens = set(t.lower() for t in re.split(r"\W+", c.memory.content or "") if len(t) >= 3)
            overlap = len(question_tokens & content_tokens) / max(len(question_tokens), 1)
            # Blend original score with lexical overlap
            blended = c.score * 0.7 + overlap * 0.3
            scored.append((blended, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        result = []
        for _, c in scored:
            c.rank = len(result) + 1
            result.append(c)
        return result


@dataclass
class RerankerConfig:
    """Configuration for the reranking pipeline."""
    enabled: bool = False
    max_candidates: int = 20
    timeout_seconds: float = 5.0


class RerankingPipeline:
    """Orchestrates optional reranking in the retrieval pipeline.

    If no reranker is configured or available, returns candidates unchanged.
    """

    def __init__(self, config: Optional[RerankerConfig] = None, reranker: Optional[Reranker] = None) -> None:
        self.config = config or RerankerConfig()
        self.reranker = reranker or IdentityReranker()

    def rerank(
        self,
        question: str,
        candidates: list[RetrievedMemory],
    ) -> list[RetrievedMemory]:
        """Apply reranking if enabled, otherwise return candidates unchanged."""
        if not self.config.enabled or not candidates:
            return candidates

        bounded = candidates[:self.config.max_candidates]
        try:
            result = self.reranker.rerank(
                question, bounded, max_candidates=self.config.max_candidates,
            )
            logger.info("Reranker %s applied to %d candidates", self.reranker.name, len(bounded))
            return result
        except Exception as exc:
            logger.warning("Reranker %s failed, falling back to original ranking: %s", self.reranker.name, exc)
            return candidates
