"""Retrieval + ranking tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database.models import Message
from app.database.repositories import ConversationRepository, MessageRepository, PersonRepository
from app.services.memory_service import MemoryService
from app.services.retrieval_service import RetrievalService
from app.utils.embeddings import hash_embedding


def _seed(db, app, texts, person_name="Ali"):
    people = PersonRepository(db)
    person = people.create(person_name)
    conversation = ConversationRepository(db).create(person.id, "t", "import")
    rows = [
        Message(conversation_id=conversation.id, person_id=person.id, sender=person_name, content=t, msg_metadata={})
        for t in texts
    ]
    MessageRepository(db).bulk_create(rows)
    db.commit()
    MemoryService(db).analyze_person(person.id, app.state.context.embeddings)
    return person


def test_retrieval_returns_relevant_memories(db, app):
    person = _seed(db, app, [
        "I prefer chai over coffee",
        "I like playing football and cricket",
        "I study computer science",
    ])
    service = RetrievalService(
        app.state.context.embeddings, app.state.context.vector_store,
        min_confidence=0.5, default_limit=5,
    )
    hits = service.retrieve(db, "what does Ali prefer to drink?", person_id=person.id)
    assert hits
    assert any("chai" in h.memory.content for h in hits)


def test_retrieval_filters_low_confidence(db, app):
    person = _seed(db, app, ["I think maybe football is okay"])
    service = RetrievalService(
        app.state.context.embeddings, app.state.context.vector_store,
        min_confidence=0.9, default_limit=5,
    )
    hits = service.retrieve(db, "what does Ali like?", person_id=person.id)
    assert hits == []  # opinions carry low confidence


def test_retrieval_respects_person_filter(db, app):
    ali = _seed(db, app, ["I prefer green tea"], person_name="Ali")
    hassan = _seed(db, app, ["I prefer black coffee"], person_name="Hassan")

    service = RetrievalService(
        app.state.context.embeddings, app.state.context.vector_store,
        min_confidence=0.5, default_limit=5,
    )
    ali_hits = service.retrieve(db, "what does Ali like to drink?", person_id=ali.id)
    assert all(h.memory.person_id == ali.id for h in ali_hits)

    hassan_hits = service.retrieve(db, "what does Ali like to drink?", person_id=hassan.id)
    assert all(h.memory.person_id == hassan.id for h in hassan_hits)


def test_retrieval_ranks_and_dedupes(db, app):
    person = _seed(db, app, [
        "I prefer chai over coffee very much a lot",
        "I prefer chai over coffee very much a lot but cold",
    ])
    service = RetrievalService(
        app.state.context.embeddings, app.state.context.vector_store,
        min_confidence=0.5, default_limit=5,
    )
    hits = service.retrieve(db, "chai coffee pref?", person_id=person.id)
    ids = [h.memory.id for h in hits]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids, key=ids.index)
    if len(hits) > 1:
        assert hits[0].rank == 1
        assert hits[0].score >= hits[1].score


def test_embedding_dim_stable():
    text = "I prefer chai over coffee"
    vector = hash_embedding(text, 384)
    assert len(vector) == 384
    mag = sum(v * v for v in vector) ** 0.5
    assert abs(mag - 1.0) < 1e-3  # unit vector