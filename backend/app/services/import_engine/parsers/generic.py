"""Generic format parser with improved tolerance and multiline support.

Handles TXT, CSV, JSON, JSONL formats with automatic detection of common
timestamp/sender patterns. Multiline messages are joined when the next line
does not match a known message pattern.
"""

from __future__ import annotations

import csv
import io
import json as jsonlib
import re
from datetime import datetime
from typing import Optional

from app.services.import_engine.normalizer import NormalizedMessage

# Common timestamp+sender line patterns
_HEADER_LINE = re.compile(
    r"^[\[\(]?\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}[\)\]]?"
)
_SENDER_COLON = re.compile(
    r"^([A-Za-z0-9_\u00C0-\u024F .'-]{1,40}):\s+(.+)$"
)
_TIMESTAMP_SENDER = re.compile(
    r"^\[?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})[,\s]+(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]m)?)\]?\s*[-\u2013]?\s*(.+?):\s(.+)$",
    re.IGNORECASE,
)

_DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%m-%Y",
    "%Y-%m-%d", "%d/%m/%y", "%m/%d/%y",
]
_TIME_FORMATS = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"]


class GenericParser:
    """Parse generic TXT, CSV, JSON, JSONL formats."""

    def parse(self, text: str, person: str = "") -> list:
        text = text.strip()
        if not text:
            return []
        if text.lstrip().startswith("{"):
            return self._parse_json(text, person)
        if text.lstrip().startswith("["):
            return self._parse_json_array(text, person)
        first_line = text.splitlines()[0] if text.splitlines() else ""
        lower = first_line.lower()
        csv_sender_cols = {"sender", "name", "author", "from", "user", "participant"}
        csv_content_cols = {"message", "text", "content", "body", "msg"}
        has_sender = any(c in lower for c in csv_sender_cols)
        has_content = any(c in lower for c in csv_content_cols)
        if has_sender and has_content:
            return self._parse_csv(text, person)
        if "," in first_line or ";" in first_line or "\t" in first_line:
            if has_content:
                return self._parse_csv(text, person)
        return self._parse_txt(text, person)

    def _parse_json(self, text: str, person: str) -> list:
        try:
            data = jsonlib.loads(text)
        except jsonlib.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        messages_raw = data.get("messages", [])
        if not isinstance(messages_raw, list):
            return []
        result = []
        for raw in messages_raw:
            if not isinstance(raw, dict):
                continue
            sender = str(raw.get("sender", "") or raw.get("sender_name", "") or raw.get("name", "") or "").strip()
            content = str(raw.get("content", "") or raw.get("text", "") or raw.get("message", "") or "").strip()
            if not sender and not content:
                continue
            ts = self._parse_ts(raw.get("timestamp") or raw.get("timestamp_ms") or raw.get("time") or raw.get("date"))
            result.append(NormalizedMessage(
                sender=sender or person or "Unknown",
                content=content,
                timestamp=ts,
                message_type=str(raw.get("message_type", "text") or "text"),
                metadata={"platform": "generic"},
            ))
        return result

    def _parse_json_array(self, text: str, person: str) -> list:
        try:
            data = jsonlib.loads(text)
        except jsonlib.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        result = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            sender = str(raw.get("sender", "") or raw.get("sender_name", "") or raw.get("name", "") or "").strip()
            content = str(raw.get("content", "") or raw.get("text", "") or raw.get("message", "") or "").strip()
            if not sender and not content:
                continue
            ts = self._parse_ts(raw.get("timestamp") or raw.get("timestamp_ms") or raw.get("time") or raw.get("date"))
            result.append(NormalizedMessage(
                sender=sender or person or "Unknown",
                content=content,
                timestamp=ts,
                message_type=str(raw.get("message_type", "text") or "text"),
                metadata={"platform": "generic"},
            ))
        return result

    def _parse_csv(self, text: str, person: str) -> list:
        # Try different delimiters
        for delimiter in (",", ";", "\t", "|"):
            text_replaced = text.replace("\r\n", "\n").replace("\r", "\n")
            reader = csv.DictReader(io.StringIO(text_replaced), delimiter=delimiter)
            if reader.fieldnames and len(reader.fieldnames) >= 2:
                break
        else:
            return []
        if reader.fieldnames is None:
            return []
        normalized = {col.strip().casefold(): col for col in reader.fieldnames}
        # Sender column aliases
        sender_aliases = {"sender", "name", "author", "from", "user", "participant", "speaker"}
        sender_col = ""
        for alias in sender_aliases:
            if alias in normalized:
                sender_col = normalized[alias]
                break
        # Content column aliases
        content_aliases = {"message", "text", "content", "body", "msg"}
        content_col = ""
        for alias in content_aliases:
            if alias in normalized:
                content_col = normalized[alias]
                break
        # Timestamp column aliases
        ts_aliases = {"timestamp", "time", "date", "created_at", "sent_at", "datetime", "ts"}
        ts_col = ""
        for alias in ts_aliases:
            if alias in normalized:
                ts_col = normalized[alias]
                break
        # Message type column
        type_aliases = {"message_type", "type", "kind"}
        type_col = ""
        for alias in type_aliases:
            if alias in normalized:
                type_col = normalized[alias]
                break
        if not content_col:
            return []
        result = []
        for row in reader:
            sender = (row.get(sender_col) or "").strip()
            content = (row.get(content_col) or "").strip()
            if not content:
                continue
            ts_str = row.get(ts_col) or None
            ts = self._parse_ts(ts_str) if ts_str else None
            msg_type = (row.get(type_col) or "text").strip() if type_col else "text"
            result.append(NormalizedMessage(
                sender=sender or person or "Unknown",
                content=content,
                timestamp=ts,
                message_type=msg_type,
                metadata={"platform": "generic"},
            ))
        return result

    def _parse_txt(self, text: str, person: str) -> list:
        lines = text.splitlines()
        messages = []
        current = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            parsed = self._try_parse_line(stripped, person)
            if parsed is not None:
                if current is not None:
                    messages.append(current)
                current = parsed
            elif current is not None:
                current.content += "\n" + stripped

        if current is not None:
            messages.append(current)
        return messages

    def _try_parse_line(self, line: str, person: str) -> Optional[NormalizedMessage]:
        m = _TIMESTAMP_SENDER.match(line)
        if m:
            ts = self._parse_timestamp_group(m.group(1), m.group(2))
            return NormalizedMessage(
                sender=m.group(3).strip(),
                content=m.group(4).strip(),
                timestamp=ts,
                metadata={"platform": "generic"},
            )
        m = _SENDER_COLON.match(line)
        if m:
            return NormalizedMessage(
                sender=m.group(1).strip(),
                content=m.group(2).strip(),
                metadata={"platform": "generic"},
            )
        return None

    def _parse_ts(self, ts) -> Optional[datetime]:
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            try:
                return datetime.fromtimestamp(float(ts))
            except (ValueError, OSError):
                return None
        if isinstance(ts, str):
            ts = ts.strip()
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        return None

    def _parse_timestamp_group(self, date_str: str, time_str: str) -> Optional[datetime]:
        combined = f"{date_str} {time_str}"
        for fmt in _DATE_FORMATS:
            for tfmt in _TIME_FORMATS:
                try:
                    return datetime.strptime(combined, f"{fmt} {tfmt}")
                except ValueError:
                    continue
        return None
