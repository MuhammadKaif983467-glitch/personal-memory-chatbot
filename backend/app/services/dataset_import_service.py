"""Full-dataset import pipeline.

Handles multi-participant conversation exports (like the Kaif/Zain synthetic
dataset) end to end:

    JSON -> validation -> message parsing -> cleaning -> duplicate detection
    -> person identification -> persistence
    -> profile generation -> writing-style analysis -> chunking
    -> memory extraction -> embeddings (vector store) -> retrieval

Two properties matter for iterative development:

* ``dry_run=True`` validates, cleans and counts but never writes anything.
* The default ``safe`` mode is idempotent: every stored message keeps a stable
  ``source_id`` from the source system, and re-importing the same dataset skips
  records that already exist. Memories and embeddings are deduplicated by the
  existing repositories (content/type match and content checksums), so running
  the dataset repeatedly never creates duplicate rows or vectors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import ImportValidationError
from app.core.logging import get_logger
from app.core.security import require_consent
from app.database.models import Message
from app.database.repositories import (
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
)
from app.schemas.import_export import DatasetImportResult, ImportedMessage
from app.services.cleaning_service import clean_imported_messages
from app.services.embedding_service import EmbeddingService
from app.services.identity_service import IdentityService
from app.services.memory_service import MemoryService

logger = get_logger("dataset_import")

# Chunking tuned for long, continuous synthetic chats: messages are ~5-10
# minutes apart, so the default 5-minute gap would create one chunk per
# message. Grouping by size instead yields coherent conversation windows.
DEFAULT_CHUNK_OPTIONS = {
    "max_chars": 2000,
    "gap_tolerance_seconds": 6 * 60 * 60,
    "min_start_chars": 2000,
}

_MAX_ERRORS = 50

# Designed-fact category -> memory type. The dataset's categories are richer
# than the memory taxonomy, so the mapping is explicit rather than inferred.
_FACT_TYPE_BY_CATEGORY = {
    "preference": "PREFERENCE",
    "drink": "PREFERENCE",
    "food": "PREFERENCE",
    "interest": "INTEREST",
    "sport": "INTEREST",
    "study": "FACT",
    "project": "FACT",
    "learning": "FACT",
    "tool": "FACT",
    "habit": "HABIT",
}

_FACT_IMPORTANCE = {
    "FACT": 0.7,
    "PREFERENCE": 0.65,
    "INTEREST": 0.65,
    "HABIT": 0.6,
}

# Confidence assigned to authoritative, structured dataset facts.
_SEEDED_CONFIDENCE = 0.85
# Confidence assigned to the current side of an explicit user correction.
_CORRECTED_CONFIDENCE = 0.95

# Memory types a correction is allowed to supersede. Conversation chunks are
# never superseded this way: they are raw history, not asserted facts.
_CORRECTABLE_TYPES = {"FACT", "PREFERENCE", "INTEREST", "HABIT"}

# --- correction interpretation ------------------------------------------------
# The dataset phrases corrections in natural language. Each rule extracts the
# old value (so the previous memory can be retired) and the new current value.
# Rules are checked in order; the first match wins.
_CORRECTION_RULES = [
    (
        "language_reconfirmation",
        re.compile(
            r"my favorite ([\w -]+?) language is still ([A-Za-z+#.]+),\s*but i am using ([A-Za-z+#.]+) more for ([\w ]+)",
            re.I,
        ),
    ),
    (
        "deadline_change",
        re.compile(r"my (.+?) deadline moved from (\w+) to (\w+)", re.I),
    ),
    (
        "exam_change",
        re.compile(r"my exam is on the (\w+),\s*not the (\w+)", re.I),
    ),
    (
        "food_change",
        re.compile(r"i said i liked (\w+) most,\s*but lately i have been choosing (\w+) more often", re.I),
    ),
    (
        "preference_change",
        re.compile(r"i (?:said i )?(?:preferred|prefer)\s+(\w+).*?but i (?:actually )?prefer\s+(\w+)", re.I),
    ),
]


@dataclass
class _ParsedDataset:
    name: str
    version: str
    title: str
    source_key: str
    participants: list[tuple[str, str]] = field(default_factory=list)
    messages: list[ImportedMessage] = field(default_factory=list)
    designed_facts: dict = field(default_factory=dict)
    corrections: list = field(default_factory=list)
    original_total: int = 0
    invalid_messages: int = 0
    duplicates_flagged: int = 0
    errors: list[str] = field(default_factory=list)


class DatasetImportService:
    def __init__(self, session: Session, settings, embeddings: Optional[EmbeddingService] = None) -> None:
        self.session = session
        self.settings = settings
        self.embeddings = embeddings

    def import_dataset(
        self,
        data: dict,
        *,
        consent_confirmed: bool,
        dry_run: bool = False,
        analyze: bool = True,
        chunk_options: Optional[dict] = None,
    ) -> DatasetImportResult:
        require_consent(consent_confirmed, self.settings)
        parsed = self._parse(data)

        # Same hard cap as the generic import path: one payload must stay
        # bounded; larger datasets are imported in chunks.
        max_messages = getattr(self.settings, "import_max_messages", 200_000)
        if parsed.original_total and parsed.original_total > max_messages:
            raise ImportValidationError(
                f"Dataset has too many messages: {parsed.original_total}. "
                f"The maximum per import is {max_messages}."
            )

        if not parsed.messages:
            raise ImportValidationError(
                "Dataset contains no valid messages.", details=parsed.errors[:_MAX_ERRORS]
            )

        cleaned, report = clean_imported_messages(parsed.messages)
        valid = len(cleaned)

        report_fields = {
            "dataset_name": parsed.name,
            "dataset_version": parsed.version,
            "total": parsed.original_total,
            "valid_messages": valid,
            "invalid_messages": parsed.invalid_messages,
            "duplicates_detected": parsed.duplicates_flagged + report.removed_duplicates,
            "removed_empty": report.removed_empty,
            "removed_duplicates": report.removed_duplicates,
            "removed_system": report.removed_system,
            "spam_flagged": report.spam_flagged,
            "cleaned": report.cleaned,
            "persons": [name for name, _ in parsed.participants] or self._senders(cleaned),
            "errors": parsed.errors[:_MAX_ERRORS],
        }

        if dry_run:
            per_person: dict = {}
            for row in cleaned:
                per_person[row.sender] = per_person.get(row.sender, 0) + 1
            return DatasetImportResult(
                mode="dry_run",
                dry_run=True,
                new_messages=0,
                skipped_existing=0,
                messages_per_person=per_person,
                **report_fields,
            )

        return self._persist(parsed, cleaned, report_fields, analyze=analyze, chunk_options=chunk_options)

    # ---- persistence ----

    def _persist(
        self,
        parsed: _ParsedDataset,
        cleaned: Sequence,
        report_fields: dict,
        *,
        analyze: bool,
        chunk_options: Optional[dict],
    ) -> DatasetImportResult:
        identity = IdentityService(self.session)

        person_by_key: dict = {}
        ordered_persons: list = []
        for name, role in parsed.participants:
            person = identity.find_or_create_person(name, relationship=role or "unknown")
            person_by_key[person.name.casefold()] = person
            ordered_persons.append(person)

        conv_repo = ConversationRepository(self.session)
        conversation = conv_repo.find_by_source(parsed.source_key)
        if conversation is None:
            primary_id = ordered_persons[0].id if ordered_persons else 1
            conversation = conv_repo.create(primary_id, parsed.title, parsed.source_key)

        msg_repo = MessageRepository(self.session)
        existing_ids = {
            str((m.msg_metadata or {}).get("source_id", ""))
            for m in msg_repo.list_by_conversation(conversation.id)
        }
        existing_ids.discard("")

        def person_for(sender: str):
            key = sender.casefold()
            if key not in person_by_key:
                person = identity.find_or_create_person(sender, relationship="unknown")
                person_by_key[key] = person
                ordered_persons.append(person)
            return person_by_key[key]

        new_rows: list[Message] = []
        per_person_new: dict = {}
        skipped_existing = 0
        for row in cleaned:
            source_id = str(row.metadata.get("source_id", ""))
            if source_id and source_id in existing_ids:
                skipped_existing += 1
                continue
            person = person_for(row.sender)
            metadata = {
                **row.metadata,
                "dataset": parsed.name,
                "dataset_version": parsed.version,
                "imported_at": _now(),
            }
            new_rows.append(
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
                    msg_metadata=metadata,
                )
            )
            if source_id:
                existing_ids.add(source_id)
            per_person_new[person.name] = per_person_new.get(person.name, 0) + 1

        for start in range(0, len(new_rows), 1000):
            msg_repo.bulk_create(new_rows[start : start + 1000])
            self.session.commit()

        timestamps = [row.timestamp for row in new_rows if row.timestamp is not None]
        if not timestamps:
            timestamps = [row.timestamp for row in cleaned if row.timestamp is not None]
        if timestamps:
            conv_repo.update_range(conversation.id, min(timestamps), max(timestamps))
        self.session.commit()

        messages_per_person = {
            person.name: msg_repo.count_for_person(person.id) for person in ordered_persons
        }

        analysis = self._analyze(ordered_persons, analyze=analyze, chunk_options=chunk_options)

        memories_before = sum(
            MemoryRepository(self.session).count_active(person.id) for person in ordered_persons
        )
        dataset_message_index = self._index_dataset_messages(conversation.id)

        seeded = self._seed_designed_facts(parsed.designed_facts, person_by_key)
        corrected = self._apply_corrections(parsed.corrections, person_by_key, dataset_message_index)
        analysis["embeddings_created"] += self._embed_active_memories(ordered_persons)

        active_memories = sum(
            MemoryRepository(self.session).count_active(person.id) for person in ordered_persons
        )

        logger.info(
            "Dataset import '%s': new=%d skipped=%d valid=%d flagged_dupes=%d memories=%d "
            "seeded=%d corrected=%d superseded=%d active=%d chunks=%d embeds=%d",
            parsed.name, len(new_rows), skipped_existing, report_fields["valid_messages"],
            parsed.duplicates_flagged, analysis["memories_created"],
            seeded["created"], corrected["created"], corrected["superseded"], active_memories,
            analysis["chunks_created"], analysis["embeddings_created"],
        )

        return DatasetImportResult(
            conversation_id=conversation.id,
            person_id=ordered_persons[0].id if ordered_persons else None,
            person_name=", ".join(person.name for person in ordered_persons),
            conversation_title=conversation.title,
            imported=len(new_rows),
            new_messages=len(new_rows),
            skipped=skipped_existing,
            skipped_existing=skipped_existing,
            messages_created=len(new_rows),
            messages_per_person=messages_per_person,
            mode="safe",
            **analysis,
            memories_before=memories_before,
            seeded_memories=seeded["created"],
            corrected_memories=corrected["created"],
            superseded_memories=corrected["superseded"],
            active_memories=active_memories,
            **report_fields,
        )

    # ---- designed facts / corrections ----

    def _index_dataset_messages(self, conversation_id: int) -> dict:
        """Map the dataset's ``message_id`` to the stored Message primary key."""
        index: dict = {}
        for message in MessageRepository(self.session).list_by_conversation(conversation_id):
            dataset_id = str((message.msg_metadata or {}).get("dataset_message_id") or "")
            if dataset_id:
                index.setdefault(dataset_id, message.id)
        return index

    def _seed_designed_facts(self, facts: dict, person_by_key: dict) -> dict:
        """Turn ``designed_memory_facts`` into real, typed Memory records."""
        created = 0
        if not isinstance(facts, dict):
            return {"created": 0}
        repo = MemoryRepository(self.session)
        for person_key, entries in facts.items():
            person = person_by_key.get(str(person_key).casefold())
            if person is None or not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                    continue
                category = str(entry[0]).strip().casefold()
                content = _tidy(str(entry[1]))
                if not content:
                    continue
                memory_type = _FACT_TYPE_BY_CATEGORY.get(category, "FACT")
                if repo.find_any(person.id, content, memory_type) is not None:
                    continue
                repo.create(
                    person_id=person.id,
                    content=content,
                    memory_type=memory_type,
                    importance=_FACT_IMPORTANCE.get(memory_type, 0.6),
                    confidence=_SEEDED_CONFIDENCE,
                    note=f"source=designed_memory_facts;category={category}",
                )
                created += 1
        self.session.commit()
        return {"created": created}

    def _apply_corrections(self, corrections: list, person_by_key: dict, message_index: dict) -> dict:
        """Apply ``intentional_corrections``.

        Each correction retires the previous memory it contradicts (never two
        active memories for the same fact) and stores the new current value
        with a back-reference so the correction history is preserved.
        """
        if not isinstance(corrections, list):
            return {"created": 0, "superseded": 0}

        repo = MemoryRepository(self.session)
        created = 0
        superseded = 0

        for correction in corrections:
            if not isinstance(correction, dict):
                continue
            sender = str(correction.get("sender") or "").strip()
            content = _tidy(str(correction.get("content") or ""))
            person = person_by_key.get(sender.casefold())
            if person is None or not content:
                continue
            dataset_id = str(correction.get("message_id") or "")
            source_message_id = message_index.get(dataset_id)

            for action in _interpret_correction(person.name, content):
                new_content = action["new_content"]
                memory_type = action["memory_type"]
                if repo.find_any(person.id, new_content, memory_type) is not None:
                    continue

                previous = self._find_previous_memory(
                    repo, person.id, action.get("old_keywords") or [], memory_type
                )
                if previous is None and action.get("old_content"):
                    previous = repo.create(
                        person_id=person.id,
                        content=action["old_content"],
                        memory_type=memory_type,
                        importance=_FACT_IMPORTANCE.get(memory_type, 0.6),
                        confidence=0.5,
                        note=(
                            "reconstructed from intentional_corrections;"
                            f"dataset_message_id={dataset_id};status=superseded"
                        ),
                    )
                    repo.set_status(previous.id, "corrected")
                    superseded += 1
                elif previous is not None and previous.status == "active":
                    previous.status = "corrected"
                    previous.note = (
                        "superseded by intentional_corrections;"
                        f"dataset_message_id={dataset_id}"
                    )
                    self.session.flush()
                    superseded += 1
                    self._remove_embedding(previous.id)

                replacement = repo.create(
                    person_id=person.id,
                    content=new_content,
                    memory_type=memory_type,
                    source_message_id=source_message_id,
                    importance=max(_FACT_IMPORTANCE.get(memory_type, 0.6), 0.75),
                    confidence=_CORRECTED_CONFIDENCE,
                    note=(
                        "source=intentional_corrections;"
                        f"dataset_message_id={dataset_id};"
                        f"replaces={previous.id if previous is not None else 'none'}"
                    ),
                    correction_of_id=previous.id if previous is not None else None,
                )
                del replacement
                created += 1

        self.session.commit()
        return {"created": created, "superseded": superseded}

    def _find_previous_memory(self, repo, person_id: int, keywords: list, memory_type: str):
        best = None
        for memory in repo.list_for_person(person_id):
            if memory.status != "active" or memory.memory_type not in _CORRECTABLE_TYPES:
                continue
            haystack = memory.content.casefold()
            if any(keyword and keyword in haystack for keyword in keywords):
                if best is None or (memory.importance or 0) > (best.importance or 0):
                    best = memory
        return best

    def _embed_active_memories(self, persons: Sequence) -> int:
        if self.embeddings is None:
            return 0
        created = 0
        for person in persons:
            for memory in MemoryRepository(self.session).list_for_person(person.id):
                if memory.status != "active":
                    continue
                if self.embeddings.ensure_memory_embedding(self.session, memory):
                    created += 1
        return created

    def _remove_embedding(self, memory_id: int) -> None:
        if self.embeddings is None:
            return
        self.embeddings.remove_memory_embedding(self.session, memory_id)

    def _analyze(self, persons: Sequence, *, analyze: bool, chunk_options: Optional[dict]) -> dict:
        result = {
            "memories_created": 0,
            "memories_extracted": 0,
            "chunks_created": 0,
            "chunks_total": 0,
            "embeddings_created": 0,
            "profile_generated": False,
            "style_generated": False,
            "warnings": [],
        }
        if not analyze or self.embeddings is None:
            return result

        options = chunk_options if chunk_options is not None else DEFAULT_CHUNK_OPTIONS
        memory_service = MemoryService(self.session)
        for person in persons:
            try:
                analysis = memory_service.analyze_person(
                    person.id, self.embeddings, chunk_options=options
                )
            except Exception as exc:  # never lose imported data over analysis
                logger.exception("Analysis failed for person=%s", person.id)
                result["warnings"].append(f"analysis failed for {person.name}: {exc}")
                continue
            result["memories_created"] += analysis.memories_created
            result["memories_extracted"] += analysis.memories_extracted
            result["chunks_created"] += analysis.chunks_created
            result["chunks_total"] += analysis.chunks_total
            result["embeddings_created"] += analysis.embeddings_created
            result["profile_generated"] = result["profile_generated"] or analysis.profile_generated
            result["style_generated"] = result["style_generated"] or analysis.style_generated
        return result

    # ---- parsing / validation ----

    def _parse(self, data: dict) -> _ParsedDataset:
        if not isinstance(data, dict):
            raise ImportValidationError("Dataset must be a JSON object.")

        raw_messages = data.get("messages")
        if not isinstance(raw_messages, list) or not raw_messages:
            raise ImportValidationError("Dataset 'messages' must be a non-empty array.")

        conversation = data.get("conversation")
        if not isinstance(conversation, dict):
            conversation = {}
        conversation_id = str(conversation.get("conversation_id") or "")
        title = str(conversation.get("title") or "Imported Dataset")
        source_base = str(conversation.get("source") or "dataset")
        version = str(data.get("version") or "")

        participants: list[tuple[str, str]] = []
        for entry in data.get("participants") or []:
            if isinstance(entry, dict):
                name = str(entry.get("name") or "").strip()
                role = str(entry.get("role") or "").strip()
            else:
                name, role = str(entry).strip(), ""
            if name:
                participants.append((name, role))

        source_parts = [source_base]
        if conversation_id:
            source_parts.append(conversation_id)
        if version:
            source_parts.append(f"v{version}")
        source_key = ":".join(source_parts)[:100]

        messages: list[ImportedMessage] = []
        invalid = 0
        flagged = 0
        errors: list[str] = []
        for index, raw in enumerate(raw_messages):
            if not isinstance(raw, dict):
                invalid += 1
                errors.append(f"messages[{index}] is not an object.")
                continue
            sender = str(raw.get("sender") or "").strip()
            if not sender:
                invalid += 1
                errors.append(f"messages[{index}] is missing a sender.")
                continue
            content = raw.get("content")
            if content is None:
                content = ""
            if not isinstance(content, str):
                invalid += 1
                errors.append(f"messages[{index}].content must be a string.")
                continue
            if raw.get("is_duplicate_test_record") is True:
                flagged += 1
                continue

            raw_id = raw.get("message_id")
            source_id = str(raw_id) if raw_id not in (None, "") else _fallback_source_id(
                sender, raw.get("timestamp"), content
            )
            messages.append(
                ImportedMessage(
                    sender=sender,
                    timestamp=raw.get("timestamp"),
                    content=content,
                    message_type=str(raw.get("message_type") or "text"),
                    source_id=source_id,
                    metadata={
                        "topic": str(raw.get("topic") or ""),
                        "dataset_message_id": str(raw_id) if raw_id not in (None, "") else "",
                    },
                )
            )

        designed_facts = data.get("designed_memory_facts")
        if not isinstance(designed_facts, dict):
            designed_facts = {}
        corrections = data.get("intentional_corrections")
        if not isinstance(corrections, list):
            corrections = []

        return _ParsedDataset(
            name=str(data.get("dataset_name") or title),
            version=version,
            title=title,
            source_key=source_key,
            participants=participants,
            messages=messages,
            designed_facts=designed_facts,
            corrections=corrections,
            original_total=len(raw_messages),
            invalid_messages=invalid,
            duplicates_flagged=flagged,
            errors=errors,
        )

    @staticmethod
    def _senders(cleaned: Sequence) -> list[str]:
        seen: list[str] = []
        for row in cleaned:
            if row.sender not in seen:
                seen.append(row.sender)
        return seen


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().strip("\"'")


def _interpret_correction(person_name: str, content: str) -> list[dict]:
    """Translate a natural-language correction into concrete memory actions.

    Returns a list of action dicts with ``new_content`` (the current value),
    ``memory_type``, ``old_keywords`` (used to find the memory being retired)
    and ``old_content`` (a reconstruction used only when the prior memory was
    never captured). Unknown phrasings return an empty list and are ignored.
    """
    for kind, pattern in _CORRECTION_RULES:
        match = pattern.search(content)
        if not match:
            continue
        groups = match.groups()

        if kind == "language_reconfirmation":
            # "my favorite quick-scripting language is still Python, but I am
            #  using C++ more for DSA" -> reaffirm Python, record the C++ shift.
            _, _current, newer, area = groups
            return [
                {
                    "kind": kind,
                    "new_content": f"{person_name} is using {newer} more for {_tidy(area)}.",
                    "memory_type": "FACT",
                    "old_keywords": [],
                    "old_content": None,
                }
            ]

        if kind == "deadline_change":
            subject, old, new = groups
            subject = _tidy(subject)
            return [
                {
                    "kind": kind,
                    "new_content": f"{person_name}'s {subject} deadline is {new}.",
                    "memory_type": "FACT",
                    "old_keywords": [old.casefold()],
                    "old_content": f"{person_name}'s {subject} deadline is {old}.",
                }
            ]

        if kind == "exam_change":
            new, old = groups
            return [
                {
                    "kind": kind,
                    "new_content": f"{person_name}'s exam is on the {new}.",
                    "memory_type": "FACT",
                    "old_keywords": [old.casefold()],
                    "old_content": f"{person_name}'s exam is on the {old}.",
                }
            ]

        if kind == "food_change":
            old, new = groups
            return [
                {
                    "kind": kind,
                    "new_content": f"{person_name} prefers {new}.",
                    "memory_type": "PREFERENCE",
                    "old_keywords": [old.casefold()],
                    "old_content": f"{person_name} likes {old}.",
                }
            ]

        if kind == "preference_change":
            old, new = groups
            return [
                {
                    "kind": kind,
                    "new_content": f"{person_name} prefers {new}.",
                    "memory_type": "PREFERENCE",
                    "old_keywords": [old.casefold()],
                    "old_content": f"{person_name} usually chooses {old}.",
                }
            ]

    return []


def _fallback_source_id(sender: str, timestamp: object, content: str) -> str:
    digest = sha1(f"{sender}|{timestamp}|{content}".encode("utf-8")).hexdigest()
    return f"gen-{digest[:24]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
