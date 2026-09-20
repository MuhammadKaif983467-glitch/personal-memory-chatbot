"""Circuit breaker unit tests."""

from __future__ import annotations

import time

from app.ai.circuit_breaker import CircuitBreaker


def test_starts_closed():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=1.0)
    assert cb.state == CircuitBreaker.CLOSED
    assert cb.allow_request() is True


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.CLOSED
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    assert cb.allow_request() is False


def test_success_resets_failure_count():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb._failure_count == 0
    assert cb.state == CircuitBreaker.CLOSED


def test_half_open_after_cooldown():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    assert cb.allow_request() is False

    time.sleep(0.15)
    assert cb.state == CircuitBreaker.HALF_OPEN
    assert cb.allow_request() is True


def test_half_open_success_closes():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.15)
    assert cb.state == CircuitBreaker.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitBreaker.CLOSED
    assert cb.allow_request() is True


def test_half_open_failure_reopens():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.15)
    assert cb.state == CircuitBreaker.HALF_OPEN
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN


def test_reset():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    cb.reset()
    assert cb.state == CircuitBreaker.CLOSED
    assert cb.allow_request() is True


def test_snapshot():
    cb = CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)
    snap = cb.snapshot()
    assert snap["state"] == "closed"
    assert snap["failure_count"] == 0
    assert snap["threshold"] == 5
    assert snap["cooldown_seconds"] == 30.0


def test_no_allow_during_cooldown():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    assert cb.allow_request() is False
    # Still within cooldown window, should remain OPEN
    time.sleep(0.05)
    assert cb.state == CircuitBreaker.OPEN
    assert cb.allow_request() is False
