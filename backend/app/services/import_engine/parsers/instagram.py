"""Instagram conversation export parser.

Handles Instagram JSON exports (message_*.json) found in ZIP archives.
Tolerates extra files in the archive - only processes conversation files.
"""

from __future__ import annotations

import json as jsonlib
import re
from datetime import datetime, timezone
from typing import Optional

from app.services.import_engine.normalizer import NormalizedMessage


def _parse_instagram_ts(ts) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(float(ts) / 1000, tz=timezone.utc)
        except (ValueError, OSError):
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


class InstagramParser:
    """Parse Instagram JSON conversation exports."""

    def parse(self, text: str, person: str = "") -> list:
        try:
            data = jsonlib.loads(text)
        except jsonlib.JSONDecodeError:
            return []

        if not isinstance(data, dict):
            return []

        participants = data.get("participants", [])
        messages_raw = data.get("messages", [])
        if not isinstance(messages_raw, list):
            return []

        result = []
        for raw in messages_raw:
            msg = self._convert(raw, participants)
            if msg is not None:
                result.append(msg)
        return result

    def _convert(self, raw: dict, participants: list) -> Optional[NormalizedMessage]:
        sender = raw.get("sender_name", "") or raw.get("from", "") or ""
        sender = str(sender).strip()
        if not sender:
            return None

        content = raw.get("content", "") or ""
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
            content = "".join(parts)
        content = str(content).strip()

        timestamp = _parse_instagram_ts(raw.get("timestamp_ms") or raw.get("timestamp"))
        msg_type = self._detect_type(raw, content)
        is_system = raw.get("type", "") == "Generic" and not content

        metadata = {"platform": "instagram"}
        if raw.get("is_still_participant") is not None:
            metadata["is_still_participant"] = raw["is_still_participant"]
        if raw.get("share"):
            metadata["share"] = raw["share"]

        reactions = []
        for r in raw.get("reactions", []):
            if isinstance(r, dict):
                emoji = r.get("reaction", "") or r.get("emoji", "")
                user = r.get("actor", "") or r.get("user", "")
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
            is_edited=bool(raw.get("is_edited")),
            reactions=reactions,
            metadata=metadata,
        )

    def _detect_type(self, raw: dict, content: str) -> str:
        if raw.get("photos") or raw.get("photo"):
            return "image"
        if raw.get("videos") or raw.get("video"):
            return "video"
        if raw.get("audio_files") or raw.get("audio"):
            return "audio"
        if raw.get("sticker"):
            return "sticker"
        if raw.get("gifs") or raw.get("gif"):
            return "image"
        if raw.get("files"):
            return "file"
        if raw.get("share"):
            return "link"
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
        if raw.get("gifs"):
            return "[GIF]"
        if raw.get("files"):
            return "[File]"
        return ""

    def parse_zip_files(self, files: list) -> list:
        """Parse Instagram conversation files from a ZIP archive."""
        messages = []
        for name, data in files:
            if not name.lower().endswith(".json"):
                continue
            if "message" not in name.lower() and "conversation" not in name.lower():
                continue
            try:
                text = data.decode("utf-8-sig", errors="replace")
                messages.extend(self.parse(text))
            except Exception:
                continue
        return messages
