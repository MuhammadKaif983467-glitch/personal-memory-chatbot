"""Tests for designed-fact seeding and intentional-correction handling.

Covers:
  * structured facts become typed Memory records bound to the right person,
  * each correction retires the previous memory and stores a current one,
  * retired (superseded) memories are never active or retrievable,
  * seeding + corrections are idempotent (no duplicate facts/embeddings).
"""

from __future__ import annotations

import pytest

from app.database.repositories import MemoryRepository, PersonRepository, StatsRepository
from app.services.dataset_import_service import DatasetImportService


def message(mid: int, sender: str, minute: int, content: str) -> dict:
    return {
        "message_id": mid,
        "conversation_id": "conv_facts_test",
        "sender": sender,
        "timestamp": f"2026-01-01T10:{minute:02d}:00",
        "content": content,
        "message_type": "text",
        "is_duplicate_test_record": False,
    }


DESIGNED_FACTS = {
    "kaif": [
        ["preference", "Kaif prefers Python for quick scripting."],
        ["interest", "Kaif follows cricket."],
        ["drink", "Kaif usually chooses tea."],
    ],
    "zain": [
        ["food", "Zain likes pizza."],
        ["project", "Zain is working on a university database project."],
    ],
}

INTENTIONAL_CORRECTIONS = [
    {
        "message_id": 1800,
        "sender": "Kaif",
        "content": "Earlier I said I preferred tea, but I actually prefer coffee now.",
    },
    {
        "message_id": 7200,
        "sender": "Zain",
        "content": "Update: I said I liked pizza most, but lately I have been choosing burgers more often.",
    },
    {
        "message_id": 3600,
        "sender": "Zain",
        "content": "Correction: my database project deadline moved from Friday to Monday.",
    },
    {
        "message_id": 9000,
        "sender": "Kaif",
        "content": "Correction: my exam is on the 25th, not the 20th.",
    },
]

MESSAGES = [
    message(1, "Kaif", 0, "Hey, how are you?"),
    message(2, "Zain", 10, "I am good, just working on stuff."),
    message(3, "Kaif", 20, "Nice, let us catch up properly later."),
    message(4, "Zain", 30, "Sure, talk soon."),
]


def make_dataset() -> dict:
    return {
        "dataset_name": "Designed Facts Test",
        "version": "1.0",
        "participants": [
            {"name": "Kaif", "role": "Friend A"},
            {"name": "Zain", "role": "Friend B"},
        ],
        "conversation": {
            "conversation_id": "conv_facts_test",
            "title": "Facts and Corrections",
            "source": "synthetic_dataset",
        },
        "designed_memory_facts": DESIGNED_FACTS,
        "intentional_corrections": INTENTIONAL_CORRECTIONS,
        "messages": MESSAGES,
    }


@pytest.fixture()
def context(app):
    return app.state.context


def people_by_name(db):
    return {person.name: person for person in PersonRepository(db).list_all()}


def imported(app, db, context):
    report = DatasetImportService(db, context.settings, context.embeddings).import_dataset(
        make_dataset(), consent_confirmed=True
    )
    return report, people_by_name(db), MemoryRepository(db)


def test_designed_facts_are_seeded_with_types_and_person(app, db, context):
    _, people, repo = imported(app, db, context)
    kaif = people["Kaif"]

    sport = repo.find_any(kaif.id, "Kaif follows cricket.", "INTEREST")
    assert sport is not None
    assert sport.person_id == kaif.id
    assert sport.memory_type == "INTEREST"
    assert sport.confidence > 0.5
    assert sport.importance > 0.5
    assert sport.created_at is not None and sport.updated_at is not None
    assert "designed_memory_facts" in sport.note

    preference = repo.find_any(kaif.id, "Kaif prefers Python for quick scripting.", "PREFERENCE")
    assert preference is not None
    assert preference.memory_type == "PREFERENCE"


def test_correction_supersedes_previous_and_creates_current(app, db, context):
    report, people, repo = imported(app, db, context)
    kaif, zain = people["Kaif"], people["Zain"]

    tea = repo.find_any(kaif.id, "Kaif usually chooses tea.", "PREFERENCE")
    coffee = repo.find_any(kaif.id, "Kaif prefers coffee.", "PREFERENCE")
    assert tea.status == "corrected"
    assert coffee.status == "active"
    assert coffee.correction_of_id == tea.id
    assert "intentional_corrections" in coffee.note

    pizza = repo.find_any(zain.id, "Zain likes pizza.", "PREFERENCE")
    burgers = repo.find_any(zain.id, "Zain prefers burgers.", "PREFERENCE")
    assert pizza.status == "corrected"
    assert burgers.status == "active"

    monday = repo.find_any(zain.id, "Zain's database project deadline is Monday.", "FACT")
    assert monday is not None and monday.status == "active"
    friday = repo.find_any(zain.id, "Zain's database project deadline is Friday.", "FACT")
    assert friday is not None and friday.status == "corrected"

    exam = repo.find_any(kaif.id, "Kaif's exam is on the 25th.", "FACT")
    old_exam = repo.find_any(kaif.id, "Kaif's exam is on the 20th.", "FACT")
    assert exam.status == "active"
    assert old_exam.status == "corrected"

    assert report.corrected_memories == 4
    assert report.superseded_memories == 4
    assert report.seeded_memories == 5


def test_no_two_active_memories_for_a_corrected_fact(app, db, context):
    _, people, repo = imported(app, db, context)
    kaif, zain = people["Kaif"], people["Zain"]

    active_contents = {
        m.content for m in repo.list_active()
    }
    assert "Kaif usually chooses tea." not in active_contents
    assert "Zain likes pizza." not in active_contents
    assert "Zain's database project deadline is Friday." not in active_contents
    assert "Kaif's exam is on the 20th." not in active_contents

    assert "Kaif prefers coffee." in active_contents
    assert "Zain prefers burgers." in active_contents
    assert "Zain's database project deadline is Monday." in active_contents
    assert "Kaif's exam is on the 25th." in active_contents


def test_retrieval_prefers_current_corrected_memory(app, db, context):
    _, people, _ = imported(app, db, context)
    kaif, zain = people["Kaif"], people["Zain"]
    retrieval = context.chat_service.retrieval

    drink_hits = retrieval.retrieve(db, "What drink does Kaif currently prefer?", person_id=kaif.id)
    assert drink_hits, "no drink memory retrieved"
    assert "coffee" in drink_hits[0].memory.content.casefold()
    assert all(h.memory.status == "active" for h in drink_hits)

    deadline_hits = retrieval.retrieve(
        db, "What is the current deadline for Zain's database project?", person_id=zain.id
    )
    assert deadline_hits
    assert "monday" in deadline_hits[0].memory.content.casefold()

    exam_hits = retrieval.retrieve(db, "What is Kaif's current exam date?", person_id=kaif.id)
    assert exam_hits
    assert "25th" in exam_hits[0].memory.content.casefold()


def test_facts_and_corrections_are_idempotent(app, db, context):
    service = DatasetImportService(db, context.settings, context.embeddings)
    dataset = make_dataset()

    first = service.import_dataset(dataset, consent_confirmed=True)
    snapshot_after_first = StatsRepository(db).snapshot()
    vectors_after_first = context.embeddings.memory_count()

    second = service.import_dataset(dataset, consent_confirmed=True)
    assert second.seeded_memories == 0
    assert second.corrected_memories == 0
    assert second.superseded_memories == 0
    assert second.embeddings_created == 0

    assert StatsRepository(db).snapshot() == snapshot_after_first
    assert context.embeddings.memory_count() == vectors_after_first

    # Exactly one active memory per current fact, regardless of reruns.
    repo = MemoryRepository(db)
    kaif = people_by_name(db)["Kaif"]
    active = [m for m in repo.list_active(kaif.id) if m.content == "Kaif prefers coffee."]
    assert len(active) == 1
    assert first.active_memories == second.active_memories
