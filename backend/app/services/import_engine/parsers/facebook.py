"""Facebook/Messenger conversation export parser.

Handles Facebook Messenger JSON exports (message_*.json) found in ZIP archives.
Tolerates extra files and folders - only processes conversation files.
"""

from __future__ import annotations

import json as jsonlib
import re
from datetime import datetime, timezone
from typing import Optional

from app.services.import_engine.normalizer import NormalizedMessage


def _parse_fb_ts(ts) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return None


class FacebookParser:
    """Parse Facebook Messenger JSON conversation exports."""

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

        participants = data.get("participants", [])
        title = data.get("title", "")

        result = []
        for raw in messages_raw:
            msg = self._convert(raw, participants)
            if msg is not None:
                result.append(msg)
        return result

    def _convert(self, raw: dict, participants: list) -> Optional[NormalizedMessage]:
        sender = raw.get("sender_name", "") or ""
        sender = str(sender).strip()
        if not sender:
            return None

        content = raw.get("content", "") or ""
        content = str(content).strip()

        timestamp = _parse_fb_ts(raw.get("timestamp_ms") or raw.get("timestamp"))
        msg_type = self._detect_type(raw, content)
        is_system = bool(raw.get("is_unsent"))

        metadata = {"platform": "facebook"}
        if raw.get("type"):
            metadata["fb_type"] = raw["type"]
        if raw.get("is_unsent"):
            metadata["is_unsent"] = True

        reactions = []
        for r in raw.get("reactions", []):
            if isinstance(r, dict):
                emoji = r.get("reaction", "")
                user = r.get("actor", "")
                if emoji:
                    reactions.append(type("Reaction", (), {"emoji": emoji, "user": str(user)})())

        content_str = content or self._media_placeholder(raw)
        if not content_str:
            return None

        return NormalizedMessage(
            sender=sender,
            content=content_str,
            timestamp=timestamp,
            message_type="system" if is_system else msg_type,
            is_system=is_system,
            is_deleted=is_system,
            reactions=reactions,
            metadata=metadata,
        )

    def _detect_type(self, raw: dict, content: str) -> str:
        if raw.get("photos"):
            return "image"
        if raw.get("videos"):
            return "video"
        if raw.get("audio_files"):
            return "audio"
        if raw.get("sticker"):
            return "sticker"
        if raw.get("files"):
            return "file"
        if raw.get("share"):
            return "link"
        if raw.get("plan"):
            return "system"
        if raw.get("calls"):
            return "system"
        if re.match(r"^https?://", content):
            return "link"
        return "text"

    def _media_placeholder(self, raw: dict) -> str:
        if raw.get("photos"):
            return "[Photo]"
        if raw.get("videos"):
            return "[Video]"
        if raw.get("audio_files"):
            return "[Audio message]"
        if raw.get("sticker"):
            return "[Sticker]"
        if raw.get("files"):
            return "[File]"
        return ""

    def parse_zip_files(self, files: list) -> list:
        """Parse Facebook conversation files from a ZIP archive."""
        messages = []
        for name, data in files:
            if not name.lower().endswith(".json"):
                continue
            if "message" not in name.lower():
                continue
            try:
                text = data.decode("utf-8-sig", errors="replace")
                msgs = self.parse(text)
                if msgs:
                    messages.extend(msgs)
            except Exception:
                continue
        return messages
