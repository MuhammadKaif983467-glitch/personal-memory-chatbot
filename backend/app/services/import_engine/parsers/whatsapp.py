"""WhatsApp chat export parser.

Handles common WhatsApp exported .txt and .zip formats with multiline
messages, media placeholders, system messages, and various date formats.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Sequence

from app.services.import_engine.normalizer import NormalizedMessage

# WhatsApp timestamp patterns (most common first)
_PATTERNS = [
    # DD/MM/YYYY, HH:MM - Sender: message
    re.compile(
        r"^(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})[,\s]+(\d{1,2}:\d{2}(?:\s?[ap]m)?)\s*[-\u2013]\s*(.+?):\s(.+)$",
        re.IGNORECASE,
    ),
    # [DD/MM/YYYY, HH:MM:SS] Sender: message
    re.compile(
        r"^\[(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})[,\s]+(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]m)?)\]\s*(.+?):\s(.+)$",
        re.IGNORECASE,
    ),
    # YYYY-MM-DD HH:MM:SS | Sender | message
    re.compile(
        r"^(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*\|\s*(.+?)\s*\|\s(.+)$",
    ),
    # YYYY-MM-DD HH:MM:SS Sender: message (Telegram-style sometimes seen)
    re.compile(
        r"^(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+?):\s(.+)$",
    ),
    # MM/DD/YY, HH:MM AM - Sender: message
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}\s*[ap]m)\s*[-\u2013]\s*(.+?):\s(.+)$",
        re.IGNORECASE,
    ),
]

# System message indicators
_SYSTEM_INDICATORS = [
    "messages and calls are end-to-end encrypted",
    "created group",
    "added you",
    "added",
    "joined using",
    "joined via invite",
    "left the group",
    "changed the subject",
    "changed this group",
    "changed the group",
    "changed the group icon",
    "removed",
    "you were added",
    "is typing",
    "security code changed",
    "deleted this message",
    "this message was deleted",
    "you deleted this message",
    "missed voice call",
    "missed video call",
    "video call",
    "voice call",
    "end-to-end encryption",
    "disappearing messages",
    "pinned a message",
    "unpinned a message",
    "now an admin",
    "no longer an admin",
    "changed their phone number",
    "is now known as",
    "you were added",
]

_MEDIA_PATTERNS = [
    (re.compile(r"<media omitted>", re.I), "media", None),
    (re.compile(r"image omitted", re.I), "image", None),
    (re.compile(r"video omitted", re.I), "video", None),
    (re.compile(r"audio omitted", re.I), "audio", None),
    (re.compile(r"sticker omitted", re.I), "sticker", None),
    (re.compile(r"gif omitted", re.I), "image", None),
    (re.compile(r"document omitted", re.I), "file", None),
    (re.compile(r"contact card omitted", re.I), "contact", None),
    (re.compile(r"location omitted", re.I), "location", None),
    (re.compile(r"IMG-\d{8}-WA\d+\.\w+", re.I), "image", None),
    (re.compile(r"VID-\d{8}-WA\d+\.\w+", re.I), "video", None),
    (re.compile(r"AUD-\d{8}-WA\d+\.\w+", re.I), "audio", None),
    (re.compile(r"PTT-\d{8}-WA\d+\.\w+", re.I), "voice", None),
    (re.compile(r"DOC-\d{8}-WA\d+\.\w+", re.I), "file", None),
    (re.compile(r"\[image\]", re.I), "image", None),
    (re.compile(r"\[video\]", re.I), "video", None),
    (re.compile(r"\[audio\]", re.I), "audio", None),
    (re.compile(r"\[sticker\]", re.I), "sticker", None),
    (re.compile(r"\[document\]", re.I), "file", None),
    (re.compile(r"\[media\]", re.I), "media", None),
]

# Date format candidates
_DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%m-%Y",
    "%Y-%m-%d", "%d/%m/%y", "%m/%d/%y", "%d.%m.%y",
    "%Y/%m/%d",
]
_TIME_FORMATS = [
    "%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p",
    "%I:%M:%S%p", "%I:%M%p",
]


class WhatsAppParser:
    """Parse WhatsApp chat exports (TXT or raw text)."""

    def parse(self, text: str, person: str = "") -> list:
        lines = text.splitlines()
        messages = []
        current_msg = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            parsed = self._parse_line(stripped, person)
            if parsed is not None:
                if current_msg is not None:
                    messages.append(current_msg)
                current_msg = parsed
            elif current_msg is not None:
                current_msg.content += "\n" + stripped

        if current_msg is not None:
            messages.append(current_msg)

        return messages

    def _parse_line(self, line: str, person: str) -> Optional[NormalizedMessage]:
        for pattern in _PATTERNS:
            m = pattern.match(line)
            if m:
                date_str, time_str, sender, content = (
                    m.group(1), m.group(2), m.group(3), m.group(4)
                )
                timestamp = self._parse_timestamp(date_str, time_str)
                msg_type, media_file = self._classify_content(content)
                is_system = self._is_system_message(sender, content)

                return NormalizedMessage(
                    sender=sender.strip(),
                    content=content.strip(),
                    timestamp=timestamp,
                    message_type="system" if is_system else msg_type,
                    is_system=is_system,
                    media_filename=media_file,
                    metadata={"platform": "whatsapp"},
                )
        return None

    def _parse_timestamp(self, date_str: str, time_str: str) -> Optional[datetime]:
        combined = f"{date_str} {time_str}"
        for fmt in _DATE_FORMATS:
            for tfmt in _TIME_FORMATS:
                try:
                    return datetime.strptime(combined, f"{fmt} {tfmt}")
                except ValueError:
                    continue
        return None

    def _classify_content(self, content: str):
        for pattern, msg_type, media_file in _MEDIA_PATTERNS:
            if pattern.search(content):
                return msg_type, media_file
        if re.match(r"^https?://", content.strip()):
            return "link", None
        return "text", None

    def _is_system_message(self, sender: str, content: str) -> bool:
        text = content.lower().strip()
        for indicator in _SYSTEM_INDICATORS:
            if indicator in text:
                return True
        return False
