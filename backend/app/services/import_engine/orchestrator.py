"""Unified import orchestrator.

Single entry point that inspects the file, selects the right parser,
normalizes messages, and produces an ImportPayload ready for ImportService.
"""

from __future__ import annotations

import io
import json as jsonlib
from typing import Optional, Sequence

from app.core.exceptions import ImportValidationError
from app.schemas.import_export import ImportPayload, ImportedConversationInfo, ImportedMessage
from app.services.import_engine.normalizer import NormalizedMessage, normalize_messages
from app.services.import_engine.participant_detector import detect_participants
from app.services.import_engine.parsers import get_parser
from app.services.import_engine.universal_inspector import UniversalInspector


MAX_PREVIEW_MESSAGES = 50
MAX_PARTICIPANTS = 100


class ImportOrchestrator:
    """Universal import orchestrator."""

    def __init__(self):
        self.inspector = UniversalInspector()

    def inspect(self, file_name: str, raw: bytes) -> dict:
        """Inspect a file and return detection results."""
        fmt = self.inspector.inspect(file_name, raw)
        return {
            "file_type": fmt.file_type,
            "platform": fmt.platform,
            "confidence": fmt.confidence,
            "inner_files": [(n, len(d)) for n, d in fmt.inner_files],
        }

    def import_file(
        self,
        file_name: str,
        raw: bytes,
        person: str = "",
        consent_confirmed: bool = False,
        project_id: Optional[int] = None,
    ) -> ImportPayload:
        """Parse a file and return an ImportPayload."""
        fmt = self.inspector.inspect(file_name, raw)
        parser_cls = get_parser(fmt.platform)
        parser = parser_cls()

        messages = self._parse_with_format(parser, fmt, raw, person)

        if not messages and fmt.platform != "generic":
            fallback_cls = get_parser("generic")
            fallback = fallback_cls()
            messages = self._parse_with_format(fallback, fmt, raw, person)

        if not messages:
            raise ImportValidationError(
                f"No parseable messages found in this {fmt.file_type.upper()} file.\n"
                f"Detected format: {fmt.file_type.upper()}\n"
                f"Detected platform: {fmt.platform}\n"
                f"Expected message fields: sender/name/author + message/text/content/body.\n"
                f"Please verify that this is a conversation export."
            )

        participants = detect_participants(messages)
        primary_person = person or (participants[0] if participants else "Unknown")
        imported_msgs = normalize_messages(messages)

        conversation_title = self._build_title(fmt.platform, participants, file_name)

        return ImportPayload(
            consent_confirmed=consent_confirmed,
            conversation=ImportedConversationInfo(
                title=conversation_title,
                person=primary_person,
                source=fmt.platform,
            ),
            messages=imported_msgs,
            project_id=project_id,
        )

    def preview_file(
        self, file_name: str, raw: bytes, person: str = ""
    ) -> dict:
        """Parse a file and return preview data."""
        fmt = self.inspector.inspect(file_name, raw)
        total_count = self._count_messages(fmt, raw)
        parser_cls = get_parser(fmt.platform)
        parser = parser_cls()
        messages = self._parse_with_format(parser, fmt, raw, person, max_rows=MAX_PREVIEW_MESSAGES)

        if not messages and fmt.platform != "generic":
            fallback_cls = get_parser("generic")
            fallback = fallback_cls()
            messages = self._parse_with_format(fallback, fmt, raw, person, max_rows=MAX_PREVIEW_MESSAGES)
        bounded = messages[:MAX_PREVIEW_MESSAGES]
        participants = detect_participants(bounded)

        preview_items = []
        for i, msg in enumerate(bounded):
            ts_str = msg.timestamp.isoformat() if msg.timestamp else ""
            preview_items.append({
                "line": i + 1,
                "sender": msg.sender,
                "timestamp": ts_str,
                "content": msg.content[:200],
                "message_type": msg.message_type,
                "issue": "system message" if msg.is_system else "",
            })

        return {
            "source": fmt.platform,
            "person": person or (participants[0] if participants else "Unknown"),
            "file_name": file_name,
            "total_records": total_count,
            "valid_messages": len([m for m in bounded if not m.is_system]),
            "malformed": 0,
            "empty": 0,
            "preview": preview_items,
            "warnings": [],
            "messages_previewed": len(preview_items),
            "participants": participants[:MAX_PARTICIPANTS],
            "platform": fmt.platform,
            "confidence": fmt.confidence,
            "is_sample": total_count > MAX_PREVIEW_MESSAGES,
        }

    def _parse_with_format(self, parser, fmt, raw: bytes, person: str, max_rows: int = 0) -> list:
        if fmt.file_type == "zip":
            return self._parse_zip(parser, fmt, raw, person)
        if fmt.file_type == "csv" and max_rows > 0:
            text = self._decode(raw)
            text = self._sample_csv(text, max_rows)
            return parser.parse(text, person=person)
        if fmt.file_type in ("json", "txt", "html", "csv"):
            text = self._decode(raw)
            return parser.parse(text, person=person)
        if fmt.file_type == "jsonl":
            text = self._decode(raw)
            if hasattr(parser, "parse"):
                return parser.parse(text, person=person)
            return []
        return []

    @staticmethod
    def _sample_csv(text: str, max_rows: int) -> str:
        lines = text.splitlines(keepends=True)
        if len(lines) <= max_rows + 1:
            return text
        return "".join(lines[:max_rows + 1])

    def _count_messages(self, fmt, raw: bytes) -> int:
        if fmt.file_type == "csv":
            try:
                text = self._decode(raw)
                return max(0, len(text.splitlines()) - 1)
            except Exception:
                return 0
        if fmt.file_type == "json":
            try:
                import json as _json
                text = self._decode(raw)
                data = _json.loads(text)
                if isinstance(data, dict) and isinstance(data.get("messages"), list):
                    return len(data["messages"])
                if isinstance(data, list):
                    return len(data)
            except Exception:
                pass
        if fmt.file_type == "jsonl":
            try:
                text = self._decode(raw)
                return len([l for l in text.splitlines() if l.strip()])
            except Exception:
                pass
        return 0

    def _parse_zip(self, parser, fmt, raw: bytes, person: str) -> list:
        if hasattr(parser, "parse_zip_files") and fmt.inner_files:
            return parser.parse_zip_files(fmt.inner_files)
        for name, data in fmt.inner_files:
            if name.lower().endswith((".txt", ".log", ".csv")):
                text = self._decode(data)
                if hasattr(parser, "parse"):
                    return parser.parse(text, person=person)
        if fmt.inner_files:
            for name, data in fmt.inner_files:
                if name.lower().endswith(".json"):
                    text = self._decode(data)
                    try:
                        jsonlib.loads(text)
                        if hasattr(parser, "parse"):
                            return parser.parse(text, person=person)
                    except Exception:
                        continue
        if fmt.inner_files:
            name, data = fmt.inner_files[0]
            text = self._decode(data)
            if hasattr(parser, "parse"):
                return parser.parse(text, person=person)
        return []

    def _decode(self, raw: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _build_title(self, platform: str, participants: list, file_name: str) -> str:
        if len(participants) == 1:
            return f"Chat with {participants[0]}"
        if len(participants) == 2:
            return f"{participants[0]} & {participants[1]}"
        if participants:
            return f"Group chat ({', '.join(participants[:3])})"
        base = file_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        for ext in (".txt", ".csv", ".json", ".zip", ".html"):
            base = base.replace(ext, "")
        return base.replace("_", " ").replace("-", " ").strip() or "Imported Chat"
