"""Structured observability for V3.4.

Provides request-level tracking, latency metrics, and privacy-aware logging.
Never logs API keys, secrets, or full private conversations.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.core.logging import get_logger

logger = get_logger("observability")


def generate_request_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    request_id: str = ""
    endpoint: str = ""
    method: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    status_code: int = 0
    db_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    provider_latency_ms: float = 0.0
    import_latency_ms: float = 0.0
    memory_latency_ms: float = 0.0
    summary_latency_ms: float = 0.0
    backup_latency_ms: float = 0.0
    error_category: str = ""
    fallback_used: bool = False

    @property
    def total_latency_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time > 0 else 0.0


class ObservabilityCollector:
    """Collects and aggregates request-level metrics."""

    def __init__(self) -> None:
        self._metrics: list[RequestMetrics] = []
        self._counters: dict[str, int] = {}

    def start_request(self, endpoint: str, method: str = "GET") -> RequestMetrics:
        m = RequestMetrics(
            request_id=generate_request_id(),
            endpoint=endpoint,
            method=method,
            start_time=time.time(),
        )
        return m

    def finish_request(self, metrics: RequestMetrics, status_code: int = 200) -> None:
        metrics.end_time = time.time()
        metrics.status_code = status_code
        self._metrics.append(metrics)
        # Keep bounded
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-500:]

    def inc(self, name: str, count: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + count

    def snapshot(self) -> dict:
        recent = self._metrics[-100:] if self._metrics else []
        avg_latency = sum(m.total_latency_ms for m in recent) / max(len(recent), 1)
        return {
            "total_requests": len(self._metrics),
            "avg_latency_ms": round(avg_latency, 1),
            "counters": dict(self._counters),
            "recent_errors": [
                {"endpoint": m.endpoint, "status": m.status_code, "error": m.error_category}
                for m in recent if m.status_code >= 400
            ][-10:],
        }


class LatencyTracker:
    """Context manager for tracking latency of operations."""

    def __init__(self, name: str, metrics: Optional[RequestMetrics] = None) -> None:
        self.name = name
        self.metrics = metrics
        self._start = 0.0

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *args):
        elapsed = (time.time() - self._start) * 1000
        if self.metrics and hasattr(self.metrics, f"{self.name}_latency_ms"):
            setattr(self.metrics, f"{self.name}_latency_ms", elapsed)
        logger.debug("%s latency: %.1fms", self.name, elapsed)
