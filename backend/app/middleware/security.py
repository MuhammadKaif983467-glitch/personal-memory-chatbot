"""Security middleware for V3.4 hardening.

Provides input sanitization and rate limiting utilities.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class InputSanitizer:
    """Sanitize user inputs to prevent injection attacks."""

    DANGEROUS_PATTERNS = [
        re.compile(r"<script\b", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"data:text/html", re.IGNORECASE),
    ]

    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)", re.IGNORECASE),
        re.compile(r"(--|;|'|\")\s*(OR|AND)\b", re.IGNORECASE),
    ]

    @classmethod
    def sanitize_text(cls, text: str, max_length: int = 10000) -> str:
        if not isinstance(text, str):
            return ""
        text = text[:max_length]
        text = text.replace("\x00", "")
        return text.strip()

    @classmethod
    def contains_xss(cls, text: str) -> bool:
        return any(p.search(text) for p in cls.DANGEROUS_PATTERNS)

    @classmethod
    def contains_sql_injection(cls, text: str) -> bool:
        return any(p.search(text) for p in cls.SQL_INJECTION_PATTERNS)

    @classmethod
    def is_safe(cls, text: str) -> bool:
        return not cls.contains_xss(text) and not cls.contains_sql_injection(text)


class RateLimiter:
    """Simple in-memory rate limiter with sliding window."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        self._cleanup(key, now)
        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        self._cleanup(key, now)
        return max(0, self.max_requests - len(self._requests[key]))


rate_limiter = RateLimiter(max_requests=500, window_seconds=60)


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.is_allowed(client_ip):
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait."}',
                status_code=429,
                media_type="application/json",
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
