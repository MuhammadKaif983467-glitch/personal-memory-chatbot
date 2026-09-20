"""Import service.

Supports:
  - JSON in the documented generic format,
  - JSONL/NDJSON (one JSON object per line),
  - CSV (sender,timestamp,content[,message_type] columns),
  - validation that rejects malformed records with useful messages instead of
    silently skipping anything,
  - consent enforcement before processing another person's data,
  - full cleaning (duplicates, empty, system, spam) with a transparent report.

The import pipeline preserves original content on every message row and then
triggers the analysis pipeline (profile/style/memories/embeddings) so the data
is immediately usable.
"""

from __future__ import annotations

import csv
import io
import json as jsonlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ImportValidationError
from app.core.logging import get_logger
from app.core.security import require_consent
from app.database.models import Message
from app.database.repositories import ConversationRepository, MessageRepository, PersonRepository
from app.schemas.import_export import ImportPayload, ImportResult, ImportedMessage
from app.services.cleaning_service import clean_imported_messages
from app.services.identity_service import IdentityService
from app.utils.validation import collect_import_errors

logger = get_logger("import")


class ImportService:
    def __init__(self, session: Session, settings) -> None:
        self.session = session
        self.settings = settings

    def import_csv(
        self,
        text: str,
        *,
        person_name: str,
        title: str,
        source: str,
        consent_confirmed: bool,
    ) -> ImportResult:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise ImportValidationError("CSV file has no header row.")
        normalized_columns = {col.strip().casefold(): col for col in reader.fieldnames}
        required = ["sender", "timestamp", "content"]
        missing = [c for c in required if c not in normalized_columns]
        if missing:
            raise ImportValidationError(
                "CSV is missing required column(s): " + ", ".join(missing)
            )

        messages: list[ImportedMessage] = []
        row_errors: list[str] = []
        for row_number, row in enumerate(reader, start=2):  # 2 = first data row
            sender = (row.get(normalized_columns.get("sender", "")) or "").strip()
            content = row.get(normalized_columns.get("content", "")) or ""
            timestamp = row.get(normalized_columns.get("timestamp", "")) or None
            message_type = row.get(normalized_columns.get("message_type", "")) or "text"
            if sender:
                messages.append(
                    ImportedMessage(sender=sender, timestamp=timestamp, content=content, message_type=message_type)
                )
            elif content.strip() or timestamp:
                row_errors.append(f"row {row_number}: sender is empty")

        if row_errors:
            raise ImportValidationError("Some rows could not be used.", details=row_errors[:15])

        payload = ImportPayload(
            consent_confirmed=consent_confirmed,
            conversation={"title": title or "Imported Chat", "person": person_name, "source": source or "csv"},
            messages=messages,
        )
        return self.import_payload(payload)

    def import_jsonl(
        self,
        text: str,
        *,
        person_name: str,
        title: str,
        source: str,
        consent_confirmed: bool,
    ) -> ImportResult:
        messages: list[ImportedMessage] = []
        row_errors: list[str] = []
        for line_num, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = jsonlib.loads(line)
            except jsonlib.JSONDecodeError as exc:
                row_errors.append(f"line {line_num}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(data, dict):
                row_errors.append(f"line {line_num}: not a JSON object")
                continue
            sender = str(data.get("sender") or "").strip()
            content = str(data.get("content") or "")
            timestamp = data.get("timestamp")
            message_type = str(data.get("message_type") or "text")
            if sender:
                messages.append(
                    ImportedMessage(sender=sender, timestamp=timestamp, content=content, message_type=message_type)
                )
            elif content.strip() or timestamp:
                row_errors.append(f"line {line_num}: sender is empty")

        if row_errors:
            raise ImportValidationError("Some lines could not be used.", details=row_errors[:15])

        payload = ImportPayload(
            consent_confirmed=consent_confirmed,
            conversation={"title": title or "Imported Chat", "person": person_name, "source": source or "jsonl"},
            messages=messages,
        )
        return self.import_payload(payload)

    def import_payload(self, payload: ImportPayload) -> ImportResult:
        require_consent(payload.consent_confirmed, self.settings)

        # Hard cap on a single payload protects the process from unbounded
        # imports; larger datasets must be imported in chunks.
        max_messages = getattr(self.settings, "import_max_messages", 200_000)
        if len(payload.messages) > max_messages:
            raise ImportValidationError(
                f"Import has too many messages: {len(payload.messages)}. "
                f"The maximum per import is {max_messages}."
            )

        # Deep validation: reject malformed records with useful messages instead
        # of silently skipping them. Stable across JSON and CSV entry points.
        errors = collect_import_errors(payload.model_dump())
        if errors:
            raise ImportValidationError(
                "Import rejected due to validation errors.", details=errors[:15]
            )

        cleaned, report = clean_imported_messages(payload.messages)
        report_errors = list(report.errors)

        identity = IdentityService(self.session)
        person = identity.find_or_create_person(payload.conversation.person, relationship="unknown")
        conversation = ConversationRepository(self.session).create(
            person.id, payload.conversation.title or "Imported Chat", payload.conversation.source
        )

        timestamps = [row.timestamp for row in cleaned if row.timestamp is not None]
        if timestamps:
            ConversationRepository(self.session).update_range(
                conversation.id, min(timestamps), max(timestamps)
            )

        rows = [
            Message(
                conversation_id=conversation.id,
                person_id=person.id,
                sender=row.sender,
                content=row.content,
                original_content=row.original_content,
                timestamp=row.timestamp,
                message_type=row.message_type,
                is_duplicate=row.is_duplicate,
                is_spam=row.is_spam,
                language=row.language,
                msg_metadata={**row.metadata, "imported_at": _now()},
            )
            for row in cleaned
        ]
        messages_created = MessageRepository(self.session).bulk_create(rows)
        self.session.commit()

        logger.info(
            "Imported conversation=%s person=%s total=%d imported=%d",
            payload.conversation.title, person.name, len(payload.messages), messages_created,
        )

        result = ImportResult(
            conversation_id=conversation.id,
            person_id=person.id,
            person_name=person.name,
            conversation_title=conversation.title,
            total=len(payload.messages),
            imported=messages_created,
            skipped=report.skipped,
            removed_empty=report.removed_empty,
            removed_duplicates=report.removed_duplicates,
            removed_system=report.removed_system,
            spam_flagged=report.spam_flagged,
            cleaned=report.cleaned,
            messages_created=messages_created,
            errors=report_errors,
        )

        # Analysis (profile/style/memories/embeddings) is triggered by the API
        # layer so the import service stays free of AI dependencies.
        return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()