"""Tests for the full multi-participant dataset import pipeline.

Focused on the guarantees that matter for iterative development:
  * dry-run writes nothing,
  * the safe mode is idempotent (no duplicate rows, memories or embeddings),
  * messages are attributed to the correct participant,
  * the analysis pipeline (profile/style/memories/embeddings) actually runs.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import ImportValidationError
from app.database.repositories import PersonRepository, StatsRepository
from app.services.dataset_import_service import DatasetImportService


def make_dataset(messages: list[dict]) -> dict:
    return {
        "dataset_name": "Unit Test Dataset",
        "version": "1.0",
        "participants": [{"name": "Kaif", "role": "Friend A"}, {"name": "Zain", "role": "Friend B"}],
        "conversation": {
            "conversation_id": "conv_unit_test",
            "title": "Kaif and Zain - Test Chat",
            "source": "synthetic_dataset",
        },
        "messages": messages,
    }


def message(mid: int, sender: str, minute: int, content: str, **extra) -> dict:
    record = {
        "message_id": mid,
        "conversation_id": "conv_unit_test",
        "sender": sender,
        "timestamp": f"2026-01-01T10:{minute:02d}:00",
        "content": content,
        "message_type": "text",
        "is_duplicate_test_record": False,
    }
    record.update(extra)
    return record


SAMPLE_MESSAGES = [
    message(1, "Kaif", 0, "I like cricket"),
    message(2, "Zain", 10, "I prefer tea over coffee"),
    message(3, "Kaif", 20, "I study at FAST University", message_type="text_emoji"),
    message(4, "Zain", 30, "I like football"),
    message(5, "Kaif", 40, "Nice 😂", message_type="text_emoji"),
    message(6, "Zain", 50, "duplicate record", is_duplicate_test_record=True),
]


@pytest.fixture()
def context(app):
    return app.state.context


def test_dry_run_writes_nothing(app, db, context):
    service = DatasetImportService(db, context.settings, context.embeddings)
    report = service.import_dataset(
        make_dataset(SAMPLE_MESSAGES), consent_confirmed=True, dry_run=True
    )

    assert report.dry_run is True
    assert report.new_messages == 0
    assert report.valid_messages == 5
    assert report.duplicates_detected == 1
    assert StatsRepository(db).snapshot()["messages"] == 0
    assert PersonRepository(db).list_all() == []


def test_import_is_idempotent(app, db, context):
    service = DatasetImportService(db, context.settings, context.embeddings)
    dataset = make_dataset(SAMPLE_MESSAGES)

    first = service.import_dataset(dataset, consent_confirmed=True)
    assert first.new_messages == 5
    assert first.valid_messages == 5
    assert first.duplicates_detected == 1
    assert first.messages_per_person == {"Kaif": 3, "Zain": 2}
    assert first.memories_created >= 3
    assert first.memories_extracted >= 3
    assert first.profile_generated is True
    assert first.style_generated is True
    assert first.embeddings_created > 0

    snapshot_after_first = StatsRepository(db).snapshot()
    vectors_after_first = context.embeddings.memory_count()

    second = service.import_dataset(dataset, consent_confirmed=True)
    assert second.new_messages == 0
    assert second.skipped_existing == 5
    assert second.memories_created == 0
    assert second.chunks_created == 0
    assert second.embeddings_created == 0

    assert StatsRepository(db).snapshot() == snapshot_after_first
    assert context.embeddings.memory_count() == vectors_after_first


def test_person_identification_and_attribution(app, db, context):
    service = DatasetImportService(db, context.settings, context.embeddings)
    service.import_dataset(make_dataset(SAMPLE_MESSAGES), consent_confirmed=True)

    people = {person.name: person for person in PersonRepository(db).list_all()}
    assert set(people) == {"Kaif", "Zain"}

    counts = StatsRepository(db).snapshot()
    assert counts["persons"] == 2
    assert counts["messages"] == 5

    # text_emoji is normalized to text, not treated as a media/file message.
    from app.database.repositories import MessageRepository

    kaif_messages = MessageRepository(db).all_for_person(people["Kaif"].id)
    assert {m.message_type for m in kaif_messages} == {"text"}


def test_retrieval_finds_extracted_memory(app, db, context):
    service = DatasetImportService(db, context.settings, context.embeddings)
    service.import_dataset(make_dataset(SAMPLE_MESSAGES), consent_confirmed=True)

    person = next(p for p in PersonRepository(db).list_all() if p.name == "Kaif")
    hits = context.chat_service.retrieval.retrieve(db, "What sport does Kaif like?", person_id=person.id)

    assert hits, "retrieval returned no memories"
    joined = " ".join(hit.memory.content.lower() for hit in hits)
    assert "cricket" in joined


def test_empty_dataset_is_rejected(app, db, context):
    service = DatasetImportService(db, context.settings, context.embeddings)
    with pytest.raises(ImportValidationError):
        service.import_dataset(
            make_dataset([]), consent_confirmed=True
        )


def test_consent_is_enforced(app, db, context):
    service = DatasetImportService(db, context.settings, context.embeddings)
    with pytest.raises(Exception):
        service.import_dataset(make_dataset(SAMPLE_MESSAGES), consent_confirmed=False)
