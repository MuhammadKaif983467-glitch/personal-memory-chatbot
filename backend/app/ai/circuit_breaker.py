"""Circuit breaker for AI provider calls.

States:
  CLOSED   -> normal operation, failures counted
  OPEN     -> provider is failing, requests blocked
  HALF_OPEN -> single probe request allowed

Transitions:
  CLOSED  -> OPEN      when consecutive failures >= threshold
  OPEN    -> HALF_OPEN when cooldown seconds elapsed
  HALF_OPEN -> CLOSED  on success
  HALF_OPEN -> OPEN    on failure
"""

from __future__ import annotations

import time

from app.core.logging import get_logger

logger = get_logger("circuit_breaker")


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        half_open_max: int = 1,
    ) -> None:
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._half_open_max = half_open_max

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_attempts = 0

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.time() - self._last_failure_time >= self._cooldown:
                self._state = self.HALF_OPEN
                self._half_open_attempts = 0
                logger.info("Circuit breaker: OPEN -> HALF_OPEN (cooldown elapsed)")
        return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == self.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == self.OPEN

    def allow_request(self) -> bool:
        s = self.state
        if s == self.CLOSED:
            return True
        if s == self.HALF_OPEN:
            return self._half_open_attempts < self._half_open_max
        return False

    def record_success(self) -> None:
        if self._state == self.HALF_OPEN:
            logger.info("Circuit breaker: HALF_OPEN -> CLOSED (probe succeeded)")
            self._state = self.CLOSED
            self._failure_count = 0
        elif self._state == self.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._last_failure_time = time.time()
        if self._state == self.HALF_OPEN:
            logger.warning("Circuit breaker: HALF_OPEN -> OPEN (probe failed)")
            self._state = self.OPEN
        elif self._state == self.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self._threshold:
                logger.warning(
                    "Circuit breaker: CLOSED -> OPEN (failures=%d >= threshold=%d)",
                    self._failure_count,
                    self._threshold,
                )
                self._state = self.OPEN

    def reset(self) -> None:
        self._state = self.CLOSED
        self._failure_count = 0
        self._half_open_attempts = 0

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "failure_count": self._failure_count,
            "threshold": self._threshold,
            "cooldown_seconds": self._cooldown,
        }
