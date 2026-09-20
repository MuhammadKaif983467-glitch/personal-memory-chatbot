"""Chunking tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.chunking_service import chunk_messages


class _FakeMessage:
    def __init__(self, message_id, content, timestamp=None, sender="person", person_id=1, conversation_id=1):
        self.id = message_id
        self.content = content
        self.timestamp = timestamp
        self.sender = sender
        self.person_id = person_id
        self.conversation_id = conversation_id


def _t(offset_minutes: int):
    return datetime(2026, 1, 1, 12, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes)


def test_consecutive_messages_grouped():
    messages = [_FakeMessage(i, f"message number {i}", _t(i)) for i in range(5)]
    chunks = chunk_messages(messages, max_chars=10_000, gap_tolerance_seconds=3600)
    assert len(chunks) == 1
    assert chunks[0].message_ids == [0, 1, 2, 3, 4]
    assert "message number 0" in chunks[0].content
    assert "message number 4" in chunks[0].content


def test_time_gap_splits_chunks():
    messages = [
        _FakeMessage(1, "alpha", _t(0)),
        _FakeMessage(2, "beta", _t(60)),   # big gap
        _FakeMessage(3, "gamma", _t(61)),
    ]
    chunks = chunk_messages(messages, max_chars=10_000, gap_tolerance_seconds=120)
    assert len(chunks) == 2
    assert chunks[0].message_ids == [1]
    assert chunks[1].message_ids == [2, 3]


def test_size_limit_splits_chunks():
    messages = [_FakeMessage(i, "x" * 100, _t(i)) for i in range(10)]
    chunks = chunk_messages(messages, max_chars=300, gap_tolerance_seconds=10_000)
    assert len(chunks) > 1
    assert all(len(c.content) <= 300 for c in chunks)


def test_sender_change_boundary():
    messages = [
        _FakeMessage(1, "short person text short", _t(0), sender="person"),
        _FakeMessage(2, "ok so I am a person too", _t(1), sender="person"),
        _FakeMessage(3, "user joined the chat", _t(2), sender="assistant"),
        _FakeMessage(4, "more person text more", _t(3), sender="person"),
    ]
    chunks = chunk_messages(messages, max_chars=10_000, gap_tolerance_seconds=3600, min_start_chars=20)
    assert len(chunks) >= 2


def test_every_chunk_keeps_source_ids():
    messages = [_FakeMessage(i, f"msg {i}", _t(i)) for i in range(7)]
    chunks = chunk_messages(messages, max_chars=60, gap_tolerance_seconds=3600)
    all_ids = [mid for chunk in chunks for mid in chunk.message_ids]
    assert sorted(all_ids) == [0, 1, 2, 3, 4, 5, 6]