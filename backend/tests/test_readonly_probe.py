"""The evaluation probe must never mutate stored data.

``ChatService.answer_preview`` runs the full retrieve -> rank -> context ->
confidence -> answer pipeline but is strictly read-only: no messages,
memories, profiles or embeddings may be created or changed.
"""

from __future__ import annotations

import pytest

from app.database.models import Conversation, Message
from app.database.repositories import PersonRepository, StatsRepository
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.dataset_import_service import DatasetImportService


def message(mid: int, sender: str, minute: int, content: str) -> dict:
    return {
        "message_id": mid,
        "conversation_id": "conv_probe_test",
        "sender": sender,
        "timestamp": f"2026-01-01T10:{minute:02d}:00",
        "content": content,
        "message_type": "text",
        "is_duplicate_test_record": False,
    }


def make_dataset() -> dict:
    return {
        "dataset_name": "Readonly Probe Test",
        "version": "1.0",
        "participants": [
            {"name": "Kaif", "role": "Friend A"},
            {"name": "Zain", "role": "Friend B"},
        ],
        "conversation": {
            "conversation_id": "conv_probe_test",
            "title": "Probe",
            "source": "synthetic_dataset",
        },
        "designed_memory_facts": {
            "kaif": [
                ["preference", "Kaif prefers coffee."],
                ["interest", "Kaif follows cricket."],
            ],
            "zain": [
                ["food", "Zain likes pizza."],
            ],
        },
        "intentional_corrections": [],
        "messages": [
            message(1, "Kaif", 0, "Hey there, how have you been?"),
            message(2, "Zain", 10, "Doing well, working on my project."),
            message(3, "Kaif", 20, "That sounds great, keep going."),
        ],
    }


@pytest.fixture()
def context(app):
    return app.state.context


def import_dataset(db, context):
    DatasetImportService(db, context.settings, context.embeddings).import_dataset(
        make_dataset(), consent_confirmed=True
    )
    return {p.name: p for p in PersonRepository(db).list_all()}


def snapshot(db, context) -> dict:
    data = dict(StatsRepository(db).snapshot())
    data["vectors"] = context.embeddings.memory_count()
    return data


def test_answer_preview_performs_zero_writes(app, db, context):
    people = import_dataset(db, context)
    before = snapshot(db, context)

    preview = context.chat_service.answer_preview(
        db, ChatRequest(person_id=people["Kaif"].id, message="What sport does Kaif follow?")
    )

    assert preview.reply
    assert preview.retrieved and preview.retrieved[0].content == "Kaif follows cricket."
    assert preview.read_only is True
    assert snapshot(db, context) == before


def test_answer_preview_creates_no_messages_or_conversations(app, db, context):
    people = import_dataset(db, context)
    conversations_before = db.query(Conversation).count()
    messages_before = db.query(Message).count()

    for question in [
        "What sport does Kaif follow?",
        "What does Kaif prefer to drink?",
        "What does Zain like to eat?",
    ]:
        context.chat_service.answer_preview(
            db, ChatRequest(person_id=people["Kaif"].id, message=question)
        )

    assert db.query(Conversation).count() == conversations_before
    assert db.query(Message).count() == messages_before
    live_rows = (
        db.query(Message).filter(Message.msg_metadata.like("%live%")).count()
    )
    assert live_rows == 0


def test_repeated_previews_are_stable_and_read_only(app, db, context):
    people = import_dataset(db, context)
    before = snapshot(db, context)
    service: ChatService = context.chat_service

    first = service.answer_preview(
        db, ChatRequest(person_id=people["Kaif"].id, message="What does Kaif prefer?")
    )
    second = service.answer_preview(
        db, ChatRequest(person_id=people["Kaif"].id, message="What does Kaif prefer?")
    )

    assert first.reply == second.reply
    assert snapshot(db, context) == before
