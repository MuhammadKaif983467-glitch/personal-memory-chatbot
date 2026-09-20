"""Data cleaning pipeline for imported chat histories.

Every imported message is preserved: the raw body stays in ``original_content``
while ``content`` holds the cleaned form. Cleaning steps:

1. whitespace normalization          5. system-message filtering
2. empty-message removal             6. message-type detection
3. duplicate detection               7. sender normalization
4. spam detection                    8. language detection (best effort)

The report returned to the caller lists exactly how many messages were dropped
or flagged so nothing is lost silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence

from app.schemas.import_export import ImportedMessage
from app.utils.text import (
    detect_language,
    is_repeat_chars,
    normalize_whitespace,
    strip_dir_marks,
)
from app.utils.timestamps import parse_timestamp

MEDIA_TYPES = {"sticker", "image", "video", "audio", "voice", "location", "contact", "file"}

_SYSTEM_SENDERS = {"system", "service", "telegram", "whatsapp", "wechat", "info"}

_SYSTEM_CONTENT_PATTERNS = [
    r"created this group",
    r"created group",
    r"added you",
    r"added yourself",
    r"joined using this group",
    r"joined via invite",
    r"changed the group",
    r"set the group",
    r"removed you",
    r"left the group",
    r"you left the group",
    r"you deleted this message",
    r"message was deleted",
    r"deleted this message",
    r"encrypted messages",
    r"disappearing messages",
    r"pinned .* message",
    r"missed (?:voice|video) call",
    r"(?:voice|video) call (?:\d|\()[^\n]*",
    r"is now known as",
    r"security code changed",
    r"you have a new",
    r"edited the group",
]


def _is_empty_content(content: str) -> bool:
    return normalize_whitespace(content) == ""


def _is_system_message(sender: str, content: str, message_type: str) -> bool:
    normalized_sender = sender.strip().casefold()
    if normalized_sender in _SYSTEM_SENDERS:
        return True
    if message_type == "system":
        return True
    text = content.casefold().strip()
    return any(re.search(pattern, text) for pattern in _SYSTEM_CONTENT_PATTERNS)


def _detect_spam(content: str, sender: str) -> bool:
    """Heuristic spam scoring; tends to over-flag nothing but obvious noise."""
    text = normalize_whitespace(content)
    if not text:
        return False
    score = 0
    if is_repeat_chars(text):
        score += 1
    upper_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if len(text) > 20 and upper_ratio > 0.7:
        score += 1
    if text.count("http") >= 2:
        score += 1
    unique_tokens = len(set(text.casefold().split()))
    if len(text.split()) > 10 and unique_tokens / len(text.split()) < 0.25:
        score += 1
    if re.search(r"\b(buy|click here|free|winner|urgent|earn)\b", text, re.I):
        score += 1
    return score >= 2


def _detect_message_type(content: str, raw_type: str) -> str:
    if raw_type in MEDIA_TYPES or raw_type == "system":
        return raw_type
    if raw_type == "text":
        return "text"
    if not content.strip():
        return "text"
    if re.match(r"^https?://", content.strip()):
        return "link"
    return "text"


def _normalize_sender(name: str) -> str:
    text = strip_dir_marks(name or "").strip()
    text = re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027B0]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^\W+|\W+$", "", text)
    return text.strip()


def _canonical_duplicate_key(sender: str, content: str, timestamp: Optional[datetime], bucket_minutes: int = 2) -> str:
    text = normalize_whitespace(content).casefold()
    if timestamp is None:
        return f"{sender}|no-ts|{text}"
    # Floor the timestamp into 2-minute buckets so near-simultaneous repeats
    # from re-exports are caught without flagging genuine later messages.
    bucket_minute = timestamp.minute - (timestamp.minute % bucket_minutes)
    rounded = timestamp.replace(minute=bucket_minute, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")
    return f"{sender}|{rounded}|{text}"


@dataclass
class CleanedMessage:
    sender: str
    original_sender: str
    timestamp: Optional[datetime]
    original_content: str
    content: str
    message_type: str
    language: str
    is_duplicate: bool
    is_spam: bool
    metadata: dict = field(default_factory=dict)


@dataclass
class CleanReport:
    total: int = 0
    kept: int = 0
    removed_empty: int = 0
    removed_duplicates: int = 0
    removed_system: int = 0
    spam_flagged: int = 0
    cleaned: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "total": self.total,
            "kept": self.kept,
            "removed_empty": self.removed_empty,
            "removed_duplicates": self.removed_duplicates,
            "removed_system": self.removed_system,
            "spam_flagged": self.spam_flagged,
            "cleaned": self.cleaned,
            "skipped": self.skipped,
        }


def clean_imported_messages(messages: Sequence[ImportedMessage]) -> tuple[Sequence[CleanedMessage], CleanReport]:
    """Run the full cleaning pipeline over imported rows.

    Returns (kept_clean_rows, report). Kept rows are ordered as imported.
    """
    report = CleanReport(total=len(messages))
    seen_keys: set[str] = set()
    kept: list[CleanedMessage] = []

    for message in messages:
        raw_content = message.content if isinstance(message.content, str) else ("" if message.content is None else str(message.content))
        cleaned_content = normalize_whitespace(raw_content)
        message_type = _detect_message_type(cleaned_content, message.message_type)

        # 1. Empty removal - but keep media messages (sticker, image, ...).
        if not cleaned_content and message_type not in MEDIA_TYPES:
            report.removed_empty += 1
            continue

        # 2. System message filtering.
        if _is_system_message(message.sender, raw_content, message_type):
            report.removed_system += 1
            continue

        # 3. Duplicate detection.
        timestamp = parse_timestamp(message.timestamp)
        sender = _normalize_sender(message.sender)
        if not sender:
            report.removed_system += 1  # unidentifiable sender
            continue
        key = _canonical_duplicate_key(sender, cleaned_content, timestamp)
        is_duplicate = key in seen_keys
        if not is_duplicate:
            seen_keys.add(key)

        # 4. Spam detection (flag, do not silently delete).
        is_spam = _detect_spam(cleaned_content, sender)

        language, _ = detect_language(cleaned_content)
        report.cleaned += 1

        kept.append(
            CleanedMessage(
                sender=sender,
                original_sender=str(message.sender or ""),
                timestamp=timestamp,
                original_content=raw_content,
                content=cleaned_content if cleaned_content else _media_placeholder(message_type),
                message_type=message_type,
                language=language,
                is_duplicate=is_duplicate,
                is_spam=is_spam,
                metadata={
                    **(getattr(message, "metadata", None) or {}),
                    "original_sender": str(message.sender or ""),
                    "original_message_type": message.message_type,
                    "source_id": getattr(message, "source_id", "") or "",
                },
            )
        )

    final_kept = [row for row in kept if not (row.is_duplicate or row.is_spam)]
    report.removed_duplicates = sum(1 for r in kept if r.is_duplicate)
    report.spam_flagged = sum(1 for r in kept if r.is_spam)
    report.kept = len(final_kept)
    report.skipped = report.removed_empty + report.removed_duplicates + report.removed_system
    return final_kept, report


def _media_placeholder(message_type: str) -> str:
    placeholders = {
        "sticker": "[sticker]",
        "image": "[image]",
        "video": "[video]",
        "audio": "[audio]",
        "voice": "[voice message]",
        "location": "[location]",
        "contact": "[contact]",
        "file": "[file]",
    }
    return placeholders.get(message_type, "[media]")


def normalize_sender(name: str) -> str:
    """Public helper reused by identity logic and tests."""
    return _normalize_sender(name)