"""Telegram chat export parser.

Handles Telegram JSON exports (result.json) and HTML exports.
Normalizes text arrays (string or entity fragments) into plain text.
"""

from __future__ import annotations

import json as jsonlib
import re
from datetime import datetime, timezone
from typing import Optional

from app.services.import_engine.normalizer import NormalizedMessage


def _flatten_text(text) -> str:
    """Flatten Telegram text which can be a string or list of fragments."""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        parts = []
        for item in text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(text) if text else ""


def _parse_telegram_ts(ts) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(ts, str):
        ts = ts.strip()
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (ValueError, OSError):
            pass
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue
    return None


class TelegramParser:
    """Parse Telegram JSON exports."""

    def parse(self, text: str, person: str = "") -> list:
        try:
            data = jsonlib.loads(text)
        except jsonlib.JSONDecodeError:
            return []

        if not isinstance(data, dict):
            return []

        messages_raw = data.get("messages", [])
        if not isinstance(messages_raw, list):
            return []

        return [msg for raw in messages_raw if (msg := self._convert(raw)) is not None]

    def _convert(self, raw: dict) -> Optional[NormalizedMessage]:
        sender = raw.get("from", "") or raw.get("actor", "") or ""
        sender = str(sender).strip()
        if not sender:
            return None

        content = _flatten_text(raw.get("text", ""))
        is_system = self._is_system(raw)

        if not content.strip() and not is_system and not raw.get("photo") and not raw.get("file"):
            return None

        timestamp = _parse_telegram_ts(raw.get("date_unixtime") or raw.get("date"))
        msg_type = self._detect_type(raw, content)
        is_system = self._is_system(raw)
        is_edited = bool(raw.get("edited"))
        is_deleted = bool(raw.get("deleted"))

        metadata = {"platform": "telegram"}
        if raw.get("forwarded_from"):
            metadata["forwarded_from"] = raw["forwarded_from"]
        if raw.get("reply_to_message_id"):
            metadata["reply_to"] = raw["reply_to_message_id"]

        reactions = []
        for r in raw.get("reactions", []):
            if isinstance(r, dict):
                emoji = r.get("type", "") or r.get("emoji", "")
                count = r.get("count", 0)
                if emoji and count:
                    reactions.append(type("Reaction", (), {"emoji": emoji, "user": f"{count} users"})())

        return NormalizedMessage(
            sender=sender,
            content=content.strip(),
            timestamp=timestamp,
            message_type="system" if is_system else msg_type,
            is_system=is_system,
            is_edited=is_edited,
            is_deleted=is_deleted,
            reactions=reactions,
            metadata=metadata,
        )

    def _detect_type(self, raw: dict, content: str) -> str:
        msg_type = raw.get("type", "")
        if msg_type in ("service",):
            return "system"
        if raw.get("photo"):
            return "image"
        if raw.get("sticker"):
            return "sticker"
        if raw.get("video"):
            return "video"
        if raw.get("voice"):
            return "voice"
        if raw.get("file"):
            return "file"
        if raw.get("location"):
            return "location"
        if raw.get("contact"):
            return "contact"
        if re.match(r"^https?://", content.strip()):
            return "link"
        return "text"

    def _is_system(self, raw: dict) -> bool:
        if raw.get("type") == "service":
            return True
        action = raw.get("action", "")
        system_actions = {
            "invite_members", "add_members", "remove_members",
            "change_title", "change_photo", "change_permissions",
            "group_created", "migrated_from", "migrated_to",
            "pinned_message", "history_cleared",
        }
        return action in system_actions
