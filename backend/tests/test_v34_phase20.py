"""V3.4 Phase 20: Security hardening tests."""

import pytest
from app.middleware.security import InputSanitizer, RateLimiter


class TestInputSanitizer:
    def test_sanitize_text_normal(self):
        assert InputSanitizer.sanitize_text("Hello world") == "Hello world"

    def test_sanitize_text_truncation(self):
        assert len(InputSanitizer.sanitize_text("a" * 20000, max_length=100)) == 100

    def test_sanitize_text_null_bytes(self):
        assert "\x00" not in InputSanitizer.sanitize_text("a\x00b")

    def test_sanitize_text_non_string(self):
        assert InputSanitizer.sanitize_text(None) == ""
        assert InputSanitizer.sanitize_text(123) == ""

    def test_xss_detection(self):
        assert InputSanitizer.contains_xss('<script>alert("xss")</script>')
        assert InputSanitizer.contains_xss('javascript:alert(1)')
        assert InputSanitizer.contains_xss('<img onerror=alert(1)>')
        assert not InputSanitizer.contains_xss("Hello world")

    def test_sql_injection_detection(self):
        assert InputSanitizer.contains_sql_injection("SELECT * FROM users")
        assert InputSanitizer.contains_sql_injection("'; DROP TABLE users; --")
        assert not InputSanitizer.contains_sql_injection("Hello world")

    def test_is_safe(self):
        assert InputSanitizer.is_safe("Hello world")
        assert not InputSanitizer.is_safe('<script>alert(1)</script>')
        assert not InputSanitizer.is_safe("SELECT * FROM users")


class TestRateLimiter:
    def test_allows_requests(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert rl.is_allowed("test")
        assert not rl.is_allowed("test")

    def test_different_keys(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        assert rl.is_allowed("a")
        assert rl.is_allowed("a")
        assert not rl.is_allowed("a")
        assert rl.is_allowed("b")

    def test_remaining(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        assert rl.remaining("test") == 5
        rl.is_allowed("test")
        assert rl.remaining("test") == 4
