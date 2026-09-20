"""Import preview service (Phase H).

Previewing must be read-only: it reports what an import *would* do without
writing a single row. TXT / CSV / ZIP files are parsed, validated and counted;
the caller decides whether to import. ZIP handling is guarded against archive
bombs, overly many members, and member files that would exhaust memory.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Optional, Sequence, Tuple

from app.core.exceptions import ImportValidationError
from app.schemas.import_export import ImportPreviewItem, ImportPreviewResult, ImportedMessage

_MAX_MEMBERS = 100
_MAX_MEMBER_SIZE = 25 * 1024 * 1024  # 25 MiB uncompressed
_MAX_TOTAL_UNCOMPRESSED = 50 * 1024 * 1024  # 50 MiB
_PREVIEW_ROWS = 20

_SENDER_LINE = re.compile(r"^\s*([A-Za-z0-9_ .'-]{1,40})\s*:\s*(.+?)\s*$")
_TIMESTAMPED_LINE = re.compile(r"^\s*\[?(\d{1,2}[:./-]\d{1,2}(?:[:./ -]\d{1,4})?)\]?\s*(.+?)\s*$")
_WHATSAPP_LINE = re.compile(
    r"^\s*\[\d{1,2}[./-]\d{1,2}[./-]\d{2,4}[,\s]+\d{1,2}[:.]\d{2}\]\s*([A-Za-z0-9_ .'-]{1,40}):\s*(.+)$"
)
_WHATSAPP_LINE_ALT = re.compile(
    r"^\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}[,\s]+\d{1,2}[:.]\d{2}\s*-\s*([A-Za-z0-9_ .'-]{1,40}):\s*(.+)$"
)


class ImportPreviewService:
    """Parse uploads and produce a read-only preview."""

    # ---- entry points ----

    def preview_file(
        self,
        file_name: str,
        raw: bytes,
        person: str = "",
        source: str = "",
    ) -> ImportPreviewResult:
        name = (file_name or "").lower()
        if name.endswith(".zip"):
            return self.preview_zip(raw, file_name=file_name, person=person)
        if name.endswith(".csv"):
            return self.preview_csv(raw, file_name=file_name, person=person)
        if name.endswith(".json"):
            return self.preview_json(raw, file_name=file_name, person=person)
        if name.endswith((".jsonl", ".ndjson")):
            return self.preview_jsonl(raw, file_name=file_name, person=person)
        return self.preview_txt(raw, file_name=file_name, person=person)

    # ---- builders ----

    def preview_txt(self, raw: bytes, *, file_name: str, person: str = "") -> ImportPreviewResult:
        text = self._decode(raw)
        items, issue_counts = self._parse_lines(text, person=person, source="txt")
        return self._assemble(
            items, issue_counts, source="txt", file_name=file_name, person=person or "Imported person"
        )

    def preview_csv(self, raw: bytes, *, file_name: str, person: str = "") -> ImportPreviewResult:
        text = self._decode(raw)
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise ImportValidationError("CSV file has no header row.")
        normalized = {col.strip().casefold(): col for col in reader.fieldnames}
        missing = [c for c in ("sender", "timestamp", "content") if c not in normalized]
        if missing:
            raise ImportValidationError("CSV is missing required column(s): " + ", ".join(missing))

        items: list[ImportPreviewItem] = []
        malformed = 0
        empty = 0
        valid = 0
        for line, row in enumerate(reader, start=2):
            sender = (row.get(normalized.get("sender", "")) or "").strip()
            content = (row.get(normalized.get("content", "")) or "").strip()
            if not content:
                empty += 1
                continue
            if not sender:
                malformed += 1
                items.append(ImportPreviewItem(line=line, content=content, issue="sender is empty"))
                continue
            valid += 1
            items.append(
                ImportPreviewItem(
                    line=line,
                    sender=sender,
                    timestamp=row.get(normalized.get("timestamp", "")) or None,
                    content=content[:200],
                    message_type=row.get(normalized.get("message_type", "")) or "text",
                )
            )
        warnings = [] if valid else ["No valid messages found in this CSV."]
        return self._assemble(
            items, {"malformed": malformed, "empty": empty, "valid": valid},
            source="csv", file_name=file_name, person=person or "Imported person",
            warnings=warnings,
        )

    def preview_json(self, raw: bytes, *, file_name: str, person: str = "") -> ImportPreviewResult:
        import json as jsonlib

        text = self._decode(raw)
        try:
            data = jsonlib.loads(text)
        except jsonlib.JSONDecodeError as exc:
            raise ImportValidationError(f"Invalid JSON: {exc.msg} at line {exc.lineno}.") from exc
        messages = data.get("messages", []) if isinstance(data, dict) else []
        items: list[ImportPreviewItem] = []
        malformed = 0
        empty = 0
        valid = 0
        for index, message in enumerate(messages, start=1):
            if not isinstance(message, dict):
                malformed += 1
                continue
            content = str(message.get("content") or "").strip()
            if not content:
                empty += 1
                continue
            sender = str(message.get("sender") or "").strip()
            if not sender:
                malformed += 1
                items.append(ImportPreviewItem(line=index, content=content[:200], issue="sender is empty"))
                continue
            valid += 1
            items.append(
                ImportPreviewItem(
                    line=index,
                    sender=sender,
                    timestamp=message.get("timestamp"),
                    content=content[:200],
                    message_type=str(message.get("message_type") or "text"),
                )
            )
        title = data.get("conversation", {}).get("person", "") if isinstance(data, dict) else ""
        return self._assemble(
            items, {"malformed": malformed, "empty": empty, "valid": valid},
            source="json", file_name=file_name, person=person or title or "Imported person",
        )

    def preview_jsonl(self, raw: bytes, *, file_name: str, person: str = "") -> ImportPreviewResult:
        import json as jsonlib

        text = self._decode(raw)
        items: list[ImportPreviewItem] = []
        malformed = 0
        empty = 0
        valid = 0
        for line_num, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                empty += 1
                continue
            try:
                message = jsonlib.loads(line)
            except jsonlib.JSONDecodeError as exc:
                malformed += 1
                items.append(ImportPreviewItem(line=line_num, issue=f"invalid JSON: {exc.msg}"))
                continue
            if not isinstance(message, dict):
                malformed += 1
                items.append(ImportPreviewItem(line=line_num, issue="not a JSON object"))
                continue
            content = str(message.get("content") or "").strip()
            if not content:
                empty += 1
                continue
            sender = str(message.get("sender") or "").strip()
            if not sender:
                malformed += 1
                items.append(ImportPreviewItem(line=line_num, content=content[:200], issue="sender is empty"))
                continue
            valid += 1
            items.append(
                ImportPreviewItem(
                    line=line_num,
                    sender=sender,
                    timestamp=message.get("timestamp"),
                    content=content[:200],
                    message_type=str(message.get("message_type") or "text"),
                )
            )
        return self._assemble(
            items, {"malformed": malformed, "empty": empty, "valid": valid},
            source="jsonl", file_name=file_name, person=person or "Imported person",
        )

    def preview_zip(self, raw: bytes, *, file_name: str, person: str = "") -> ImportPreviewResult:
        member = self._pick_zip_member(raw)
        inner_name = member[0]
        inner_raw = member[1]
        inner_person = person or self.name_without_zip(inner_name)
        if inner_name.endswith(".csv"):
            return self.preview_csv(inner_raw, file_name=inner_name, person=inner_person)
        if inner_name.endswith(".json"):
            return self.preview_json(inner_raw, file_name=inner_name, person=inner_person)
        if inner_name.endswith((".jsonl", ".ndjson")):
            return self.preview_jsonl(inner_raw, file_name=inner_name, person=inner_person)
        return self.preview_txt(inner_raw, file_name=inner_name, person=inner_person)

    # ---- import helpers (shared with the API layer) ----

    def txt_to_messages(self, raw: bytes, *, person: str = "") -> Sequence[ImportedMessage]:
        text = self._decode(raw)
        messages: list[ImportedMessage] = []
        for line in self._non_empty_lines(text):
            sender, content = self._split_line(line, person)
            if not content:
                continue
            messages.append(ImportedMessage(sender=sender, content=content[:4000]))
        if not messages:
            raise ImportValidationError("The file contains no parseable messages.")
        return messages

    def zip_to_messages(self, raw: bytes, *, person: str = "") -> Sequence[ImportedMessage]:
        inner_name, inner_raw = self._pick_zip_member(raw, largest=True)
        if inner_name.endswith(".csv"):
            text = self._decode(inner_raw)
            reader = csv.DictReader(io.StringIO(text))
            normalized = {col.strip().casefold(): col for col in (reader.fieldnames or [])}
            sender_col = normalized.get("sender", "")
            content_col = normalized.get("content", "")
            messages = [
                ImportedMessage(sender=row.get(sender_col, "") or person, content=row.get(content_col, "") or "")
                for row in reader
                if (row.get(content_col) or "").strip()
            ]
            if not messages:
                raise ImportValidationError("The CSV inside the ZIP contains no messages.")
            return messages
        if inner_name.endswith(".json"):
            import json as jsonlib

            data = jsonlib.loads(inner_raw.decode("utf-8-sig", errors="replace"))
            raw_messages = data.get("messages", []) if isinstance(data, dict) else []
            messages = [
                ImportedMessage(
                    sender=str(m.get("sender") or person),
                    timestamp=m.get("timestamp"),
                    content=str(m.get("content") or ""),
                )
                for m in raw_messages
                if isinstance(m, dict) and str(m.get("content") or "").strip()
            ]
            if not messages:
                raise ImportValidationError("The JSON inside the ZIP contains no messages.")
            return messages
        if inner_name.endswith((".jsonl", ".ndjson")):
            import json as jsonlib

            text = inner_raw.decode("utf-8-sig", errors="replace")
            raw_messages = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_messages.append(jsonlib.loads(line))
                except jsonlib.JSONDecodeError:
                    continue
            messages = [
                ImportedMessage(
                    sender=str(m.get("sender") or person),
                    timestamp=m.get("timestamp"),
                    content=str(m.get("content") or ""),
                )
                for m in raw_messages
                if isinstance(m, dict) and str(m.get("content") or "").strip()
            ]
            if not messages:
                raise ImportValidationError("The JSONL inside the ZIP contains no messages.")
            return messages
        return self.txt_to_messages(inner_raw, person=person or self.name_without_zip(inner_name))

    # ---- internals ----

    def _assemble(
        self,
        items: Sequence[ImportPreviewItem],
        issue_counts: dict,
        *,
        source: str,
        file_name: str,
        person: str,
        warnings: Optional[Sequence[str]] = None,
    ) -> ImportPreviewResult:
        valid = issue_counts.get("valid", len([i for i in items if not i.issue]))
        return ImportPreviewResult(
            source=source,
            person=person,
            file_name=file_name,
            total_records=valid + issue_counts.get("malformed", 0) + issue_counts.get("empty", 0),
            valid_messages=valid,
            malformed=issue_counts.get("malformed", 0),
            empty=issue_counts.get("empty", 0),
            preview=list(items)[:_PREVIEW_ROWS],
            warnings=list(warnings or []),
            messages_previewed=len(items),
        )

    def _parse_lines(
        self, text: str, *, person: str, source: str
    ) -> Tuple[Sequence[ImportPreviewItem], dict]:
        items: list[ImportPreviewItem] = []
        valid = 0
        empty = 0
        malformed = 0
        for line, raw_line in enumerate(self._non_empty_lines(text), start=1):
            sender, content = self._split_line(raw_line, person)
            item_content = content
            if not content:
                empty += 1
                items.append(ImportPreviewItem(line=line, issue="empty line"))
                continue
            # A line with no detectable sender still previews (assigned to the
            # person) but is flagged so the user knows attribution is guessed.
            issue = "" if sender and sender != person else "sender guessed from file name"
            if not sender and not person:
                malformed += 1
                issue = "no sender and no person provided"
            else:
                valid += 1
            if len(items) < _PREVIEW_ROWS or issue:
                items.append(
                    ImportPreviewItem(
                        line=line, sender=sender or person, content=item_content[:200], issue=issue
                    )
                )
        return items, {"malformed": malformed, "empty": empty, "valid": valid}

    def _split_line(self, line: str, person: str) -> Tuple[str, str]:
        match = _WHATSAPP_LINE.match(line)
        if match:
            sender = match.group(1).strip()
            content = match.group(2).strip()
            if content:
                return sender, content
        match = _WHATSAPP_LINE_ALT.match(line)
        if match:
            sender = match.group(1).strip()
            content = match.group(2).strip()
            if content:
                return sender, content
        match = _SENDER_LINE.match(line)
        if match:
            sender = match.group(1).strip()
            content = match.group(2).strip()
            if content:
                return sender, content
        match = _TIMESTAMPED_LINE.match(line)
        if match:
            return person, match.group(2).strip()
        return person, line.strip()

    def _non_empty_lines(self, text: str) -> Sequence[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _pick_zip_member(
        self, raw: bytes, *, largest: bool = True
    ) -> Tuple[str, bytes]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            raise ImportValidationError("Uploaded file is not a valid ZIP archive.") from exc
        with archive:
            names = archive.namelist()
            if len(names) > _MAX_MEMBERS:
                raise ImportValidationError(f"ZIP contains too many files (>{_MAX_MEMBERS}).")
            candidates = [n for n in names if not n.startswith(("__MACOSX", "._"))]
            text_members = [
                n for n in candidates if n.lower().endswith((".txt", ".csv", ".log", ".json", ".jsonl", ".ndjson"))
            ]
            if not text_members:
                raise ImportValidationError(
                    "No text (.txt/.csv/.json/.jsonl/.ndjson) files found inside the ZIP."
                )
            if largest:
                text_members.sort(
                    key=lambda n: archive.getinfo(n).file_size, reverse=True
                )
            name = text_members[0]
            info = archive.getinfo(name)
            if info.file_size > _MAX_MEMBER_SIZE:
                raise ImportValidationError(f"ZIP member '{name}' is too large to import.")
            if sum(getattr(i, "file_size", 0) for i in archive.infolist()) > _MAX_TOTAL_UNCOMPRESSED:
                raise ImportValidationError("ZIP expands to more than 50 MB; refusing to import.")
            try:
                member_raw = archive.read(name)
            except Exception as exc:  # noqa: BLE001 - zipfile is defensive here
                raise ImportValidationError(f"Could not read ZIP member '{name}'.") from exc
        return name.rsplit("/", 1)[-1], member_raw

    def _decode(self, raw: bytes) -> str:
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def name_without_zip(name: str) -> str:
        base = name.rsplit("/", 1)[-1]
        for suffix in (".txt", ".csv", ".json", ".log"):
            if base.lower().endswith(suffix):
                base = base[: -len(suffix)]
        return base.replace("_", " ").replace("-", " ").strip() or "Imported person"