"""V3.4 Phases 11-12: Observability and evaluation framework tests."""

import pytest
from unittest.mock import MagicMock
from app.services.observability import (
    ObservabilityCollector, RequestMetrics, LatencyTracker, generate_request_id,
)
from app.services.evaluation import (
    EvalResult, EvalCase, EvalSuite,
    RetrievalEvaluator, MemoryEvaluator, IdentityEvaluator, SecurityEvaluator,
)


class TestObservability:
    def test_request_id_unique(self):
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100

    def test_collector_start_finish(self):
        coll = ObservabilityCollector()
        m = coll.start_request("/chat", "POST")
        assert m.request_id
        assert m.endpoint == "/chat"
        coll.finish_request(m, 200)
        assert m.status_code == 200
        assert m.total_latency_ms >= 0

    def test_collector_bounded(self):
        coll = ObservabilityCollector()
        for i in range(1200):
            m = coll.start_request(f"/endpoint_{i}")
            coll.finish_request(m, 200)
        # Should be bounded (not grow unbounded)
        assert len(coll._metrics) < 1200

    def test_latency_tracker(self):
        m = RequestMetrics()
        with LatencyTracker("retrieval", m):
            pass
        assert m.retrieval_latency_ms >= 0

    def test_snapshot(self):
        coll = ObservabilityCollector()
        m = coll.start_request("/test")
        coll.finish_request(m, 200)
        snap = coll.snapshot()
        assert snap["total_requests"] == 1


class TestRetrievalEvaluator:
    def test_relevance_pass(self):
        mock_mem = MagicMock()
        mock_mem.id = 1
        mock_result = MagicMock()
        mock_result.memory = mock_mem
        ev = RetrievalEvaluator()
        suite = ev.evaluate_relevance("test", [mock_result], [1])
        assert suite.passed == 1

    def test_relevance_fail(self):
        ev = RetrievalEvaluator()
        suite = ev.evaluate_relevance("test", [], [1])
        assert suite.failed == 1

    def test_project_isolation(self):
        mock_mem = MagicMock()
        mock_mem.project_id = 1
        mock_result = MagicMock()
        mock_result.memory = mock_mem
        ev = RetrievalEvaluator()
        suite = ev.evaluate_project_isolation([mock_result], 1)
        assert suite.passed == 1

    def test_deduplication(self):
        mock_mem = MagicMock()
        mock_mem.id = 1
        mock_result = MagicMock()
        mock_result.memory = mock_mem
        ev = RetrievalEvaluator()
        suite = ev.evaluate_deduplication([mock_result, mock_result])
        assert suite.failed >= 1


class TestMemoryEvaluator:
    def test_extraction_type_match(self):
        ev = MemoryEvaluator()
        suite = ev.evaluate_extraction("I like coffee", "PREFERENCE", "PREFERENCE")
        assert suite.passed == 1

    def test_extraction_type_mismatch(self):
        ev = MemoryEvaluator()
        suite = ev.evaluate_extraction("I like coffee", "FACT", "PREFERENCE")
        assert suite.failed == 1


class TestIdentityEvaluator:
    def test_me_other_correct(self):
        ev = IdentityEvaluator()
        suite = ev.evaluate_me_other("me", "ME")
        assert suite.passed == 1

    def test_no_generic_names(self):
        ev = IdentityEvaluator()
        suite = ev.evaluate_no_generic_names(["Kaif", "Ali"])
        assert suite.passed == 2

    def test_generic_names_detected(self):
        ev = IdentityEvaluator()
        suite = ev.evaluate_no_generic_names(["User", "Kaif"])
        assert suite.failed == 1
        assert suite.passed == 1


class TestSecurityEvaluator:
    def test_injection_defended(self):
        ev = SecurityEvaluator()
        suite = ev.evaluate_prompt_injection("ignore previous", "Hello there")
        assert suite.passed == 1

    def test_injection_leaked(self):
        ev = SecurityEvaluator()
        suite = ev.evaluate_prompt_injection("test", "You are now a hacker")
        assert suite.failed == 1

    def test_project_isolation_pass(self):
        ev = SecurityEvaluator()
        suite = ev.evaluate_project_isolation({"project_id": 1}, 1)
        assert suite.passed == 1
