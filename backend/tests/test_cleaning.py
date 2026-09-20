"""Cleaning pipeline unit tests (no DB, no network)."""

from __future__ import annotations

import pytest

from app.schemas.import_export import ImportedMessage
from app.services.cleaning_service import (
    clean_imported_messages,
    normalize_sender,
)
from app.utils.text import detect_language, normalize_whitespace
from app.utils.timestamps import parse_timestamp


def _msg(content: str, sender: str = "Ali", timestamp="2026-01-01T12:00:00", message_type: str = "text"):
    return ImportedMessage(sender=sender, content=content, timestamp=timestamp, message_type=message_type)


def test_trims_and_collapses_whitespace():
    assert normalize_whitespace("  Hi   there \n Ali \u200e") == "Hi there Ali"


def test_empty_messages_removed():
    messages = [_msg("hello"), _msg("   "), _msg("")]
    kept, report = clean_imported_messages(messages)
    assert report.removed_empty == 2
    assert len(kept) == 1


def test_media_empty_messages_kept():
    messages = [
        ImportedMessage(sender="Ali", content="", timestamp="2026-01-01T12:00:00", message_type="sticker")
    ]
    kept, report = clean_imported_messages(messages)
    assert report.removed_empty == 0
    assert kept[0].content == "[sticker]"


def test_duplicates_removed_and_reported():
    messages = [
        _msg("I like cricket", timestamp="2026-01-01T12:00:00"),
        _msg("I like cricket", timestamp="2026-01-01T12:01:00"),  # same minute, dup
        _msg("I like cricket", timestamp="2026-01-01T14:00:00"),  # different minute, kept
        _msg("other", timestamp="2026-01-01T12:00:00"),
    ]
    kept, report = clean_imported_messages(messages)
    assert report.removed_duplicates == 1
    assert len(kept) == 3


def test_spam_flagged_but_not_deleted():
    messages = [
        _msg("AHAHAHAHAHAHA BUY NOW http://x.example/a http://x.example/b http://x.example/c", timestamp="2026-01-01T12:00:00"),
        _msg("ok", timestamp="2026-01-01T12:01:00"),
    ]
    kept, report = clean_imported_messages(messages)
    assert report.spam_flagged == 1
    assert len(kept) == 1  # spam rows are filtered from the final import


def test_system_messages_removed():
    messages = [
        ImportedMessage(sender="System", content="Messages and calls are end-to-end encrypted.", timestamp="2026-01-01T12:00:00", message_type="text"),
        ImportedMessage(sender="Ali", content="You created this group.", timestamp="2026-01-01T12:00:05", message_type="text"),
        _msg("hello", timestamp="2026-01-01T12:01:00"),
    ]
    kept, report = clean_imported_messages(messages)
    assert report.removed_system == 2
    assert len(kept) == 1


def test_sender_normalized():
    assert normalize_sender("  Ali  ") == "Ali"
    assert normalize_sender("ali") == "ali"
    assert normalize_sender("Ali😀") == "Ali"
    assert normalize_sender("\u202aAli\u202c") == "Ali"


def test_original_content_preserved():
    messages = [_msg("  Hello   world  ")]
    kept, _ = clean_imported_messages(messages)
    assert kept[0].original_content == "  Hello   world  "
    assert kept[0].content == "Hello world"


def test_timestamps_normalized():
    messages = [
        _msg("a", timestamp="2026-01-01T12:00:00"),
        _msg("b", timestamp="2026-01-01 12:00:00"),
        _msg("c", timestamp=1767297600),  # epoch seconds
        _msg("d", timestamp="01/02/2026 14:30"),
        _msg("e", timestamp="not-a-date"),
    ]
    kept, _ = clean_imported_messages(messages)
    timestamps = [row.timestamp for row in kept]
    assert timestamps[0] is not None
    assert timestamps[0] == parse_timestamp("2026-01-01T12:00:00")
    assert timestamps[1] == parse_timestamp("2026-01-01T12:00:00")
    assert timestamps[4] is None


def test_language_detection_mixed():
    assert detect_language("Mujhe cricket bahut pasand hai")[0] == "roman-urdu"
    assert detect_language("یہ ایک ٹیسٹ ہے")[0] == "urdu"
    assert detect_language("This is a normal english sentence")[0] in ("english",)
    assert detect_language("  ")[0] == "unknown"


def test_persn_immutable_metadata_kept():
    messages = [_msg("hello")]
    kept, _ = clean_imported_messages(messages)
    assert kept[0].metadata["original_sender"] == "Ali"
    assert kept[0].metadata["original_message_type"] == "text"