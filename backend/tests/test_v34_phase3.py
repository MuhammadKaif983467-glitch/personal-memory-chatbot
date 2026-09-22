"""V3.4 Phase 3: Optional retrieval reranking tests."""

import pytest
from unittest.mock import MagicMock
from app.services.reranker import (
    Reranker, IdentityReranker, LexicalReranker, RerankerConfig, RerankingPipeline,
)
from app.services.retrieval_service import RetrievedMemory


def _mock_memory(content: str, mem_id: int = 1) -> MagicMock:
    m = MagicMock()
    m.id = mem_id
    m.content = content
    m.status = "active"
    m.confidence = 0.8
    m.importance = 0.5
    m.memory_type = "FACT"
    return m


def _make_retrieved(content: str, score: float = 0.5, mem_id: int = 1) -> RetrievedMemory:
    return RetrievedMemory(
        memory=_mock_memory(content, mem_id),
        similarity=score,
        score=score,
        rank=0,
    )


class TestIdentityReranker:
    def test_preserves_order(self):
        reranker = IdentityReranker()
        items = [_make_retrieved("a", 0.9, 1), _make_retrieved("b", 0.5, 2)]
        result = reranker.rerank("query", items)
        assert len(result) == 2
        assert result[0].memory.content == "a"

    def test_truncates(self):
        reranker = IdentityReranker()
        items = [_make_retrieved(f"item{i}", 0.9 - i * 0.1, i) for i in range(5)]
        result = reranker.rerank("query", items, max_candidates=3)
        assert len(result) == 3


class TestLexicalReranker:
    def test_boosts_overlapping_content(self):
        reranker = LexicalReranker()
        items = [
            _make_retrieved("coffee is great", 0.5, 1),
            _make_retrieved("random unrelated text", 0.6, 2),
        ]
        result = reranker.rerank("coffee great", items)
        assert result[0].memory.content == "coffee is great"

    def test_empty_query(self):
        reranker = LexicalReranker()
        items = [_make_retrieved("hello", 0.5, 1)]
        result = reranker.rerank("", items)
        assert len(result) == 1


class TestRerankingPipeline:
    def test_disabled_returns_original(self):
        config = RerankerConfig(enabled=False)
        pipeline = RerankingPipeline(config=config)
        items = [_make_retrieved("a", 0.9, 1), _make_retrieved("b", 0.5, 2)]
        result = pipeline.rerank("query", items)
        assert result is items

    def test_enabled_applies_reranker(self):
        config = RerankerConfig(enabled=True, max_candidates=10)
        pipeline = RerankingPipeline(config=config, reranker=IdentityReranker())
        items = [_make_retrieved("a", 0.9, 1), _make_retrieved("b", 0.5, 2)]
        result = pipeline.rerank("query", items)
        assert len(result) == 2

    def test_fallback_on_reranker_failure(self):
        class FailingReranker(Reranker):
            name = "failing"
            def rerank(self, question, candidates, *, max_candidates=20):
                raise RuntimeError("reranker crashed")

        config = RerankerConfig(enabled=True)
        pipeline = RerankingPipeline(config=config, reranker=FailingReranker())
        items = [_make_retrieved("a", 0.9, 1)]
        result = pipeline.rerank("query", items)
        assert result is items

    def test_empty_candidates(self):
        config = RerankerConfig(enabled=True)
        pipeline = RerankingPipeline(config=config)
        result = pipeline.rerank("query", [])
        assert result == []
