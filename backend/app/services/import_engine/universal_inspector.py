"""Universal file inspector: detects format and platform from file content."""

from __future__ import annotations

import io
import json as jsonlib
import zipfile
from dataclasses import dataclass
from typing import Optional


@dataclass
class DetectedFormat:
    file_type: str  # txt, csv, json, jsonl, zip, html
    platform: str  # whatsapp, telegram, instagram, facebook, generic
    confidence: float  # 0.0 - 1.0
    inner_files: list = None  # list of (name, bytes) for ZIP contents

    def __post_init__(self):
        if self.inner_files is None:
            self.inner_files = []


class UniversalInspector:
    """Inspect uploaded file to detect format and platform."""

    def inspect(self, file_name: str, raw: bytes) -> DetectedFormat:
        name = (file_name or "").lower()

        if name.endswith(".zip"):
            return self._inspect_zip(raw, name)
        if name.endswith(".csv"):
            return DetectedFormat("csv", "generic", 0.9)
        if name.endswith((".jsonl", ".ndjson")):
            return DetectedFormat("jsonl", "generic", 0.9)
        if name.endswith(".json"):
            return self._inspect_json(raw)
        if name.endswith((".html", ".htm")):
            return self._inspect_html(raw, name)
        return self._inspect_text(raw, name)

    def _inspect_zip(self, raw: bytes, name: str) -> DetectedFormat:
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            return DetectedFormat("zip", "generic", 0.3)
        with archive:
            names = archive.namelist()
            inner = []
            for n in names:
                if n.startswith(("__MACOSX", "._")):
                    continue
                try:
                    data = archive.read(n)
                    inner.append((n.rsplit("/", 1)[-1], data))
                except Exception:
                    continue

            platform = self._detect_platform_from_files(inner)
            return DetectedFormat("zip", platform, 0.9, inner_files=inner)

    def _inspect_json(self, raw: bytes) -> DetectedFormat:
        try:
            text = raw.decode("utf-8-sig", errors="replace")
            data = jsonlib.loads(text)
        except (jsonlib.JSONDecodeError, UnicodeDecodeError):
            return DetectedFormat("json", "generic", 0.3)
        if not isinstance(data, dict):
            return DetectedFormat("json", "generic", 0.5)
        platform = self._detect_platform_from_dict(data)
        return DetectedFormat("json", platform, 0.8)

    def _inspect_html(self, raw: bytes, name: str) -> DetectedFormat:
        try:
            text = raw.decode("utf-8-sig", errors="replace")[:10000]
        except UnicodeDecodeError:
            return DetectedFormat("html", "generic", 0.3)
        lower = text.lower()
        if "whatsapp" in lower:
            return DetectedFormat("html", "whatsapp", 0.9)
        if "telegram" in lower:
            return DetectedFormat("html", "telegram", 0.9)
        if "instagram" in lower:
            return DetectedFormat("html", "instagram", 0.9)
        if "facebook" in lower or "messenger" in lower:
            return DetectedFormat("html", "facebook", 0.9)
        return DetectedFormat("html", "generic", 0.5)

    def _inspect_text(self, raw: bytes, name: str) -> DetectedFormat:
        try:
            text = raw.decode("utf-8-sig", errors="replace")[:15000]
        except UnicodeDecodeError:
            return DetectedFormat("txt", "generic", 0.3)
        platform = self._detect_platform_from_text(text)
        return DetectedFormat("txt", platform, 0.8)

    def _detect_platform_from_files(self, files: list) -> str:
        names_lower = [n.lower() for n, _ in files]
        all_text = " ".join(names_lower)
        if "message" in all_text and any("html" in n for n in names_lower):
            if any("whatsapp" in n for n in names_lower):
                return "whatsapp"
            if any("telegram" in n for n in names_lower):
                return "telegram"
        if any("result.json" in n or "message.json" in n for n in names_lower):
            return "facebook"
        if any(n.endswith(".html") for n in names_lower):
            for name, data in files:
                if name.lower().endswith(".html"):
                    try:
                        snippet = data.decode("utf-8", errors="replace")[:5000].lower()
                        if "whatsapp" in snippet:
                            return "whatsapp"
                        if "telegram" in snippet:
                            return "telegram"
                        if "instagram" in snippet:
                            return "instagram"
                        if "facebook" in snippet or "messenger" in snippet:
                            return "facebook"
                    except Exception:
                        continue
        for name, data in files:
            if name.lower().endswith(".json"):
                try:
                    d = jsonlib.loads(data.decode("utf-8", errors="replace"))
                    if isinstance(d, dict):
                        detected = self._detect_platform_from_dict(d)
                        if detected != "generic":
                            return detected
                except Exception:
                    continue
        return "generic"

    def _detect_platform_from_dict(self, data: dict) -> str:
        keys = set(data.keys())
        if "messages" in keys and isinstance(data["messages"], list):
            msgs = data["messages"]
            if msgs and isinstance(msgs[0], dict):
                msg_keys = set(msgs[0].keys())
                if "from" in msg_keys and "text" in msg_keys and "date" in msg_keys:
                    return "telegram"
                if ("sender_name" in msg_keys or "timestamp_ms" in msg_keys) and "content" in msg_keys:
                    return "facebook"
                if "sender" in msg_keys and "text" in msg_keys:
                    return "generic"
                if "sender" in msg_keys and "content" in msg_keys:
                    return "generic"
        if "participants" in keys and "messages" in keys:
            msgs = data.get("messages", [])
            if msgs and isinstance(msgs[0], dict):
                msg_keys = set(msgs[0].keys())
                if ("sender_name" in msg_keys or "timestamp_ms" in msg_keys) and "content" in msg_keys:
                    return "facebook"
            return "generic"
        if "chats" in keys:
            return "telegram"
        return "generic"

    def _detect_platform_from_text(self, text: str) -> str:
        lines = text.strip().splitlines()[:50]
        sample = "\n".join(lines)
        whatsapp_patterns = [
            r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}[,\s]+\d{1,2}[:.]\d{2}",
            r"\[\d{1,2}[./-]\d{1,2}[./-]\d{2,4}",
        ]
        import re
        for pat in whatsapp_patterns:
            matches = re.findall(pat, sample)
            if len(matches) >= 2:
                return "whatsapp"
        if re.search(r"\[\d{4}-\d{2}-\d{2}", sample):
            return "telegram"
        if re.search(r"\d{1,2}:\d{2}\s*(AM|PM|am|pm)", sample):
            return "whatsapp"
        return "generic"
