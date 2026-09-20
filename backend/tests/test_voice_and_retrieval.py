"""Voice capability reporting (Phase V) + hybrid retrieval upgrades (Phase P).

Voice must never be a hard dependency: the status endpoint reports what is
available and the product works with everything disabled. Retrieval now falls
back to lexical search when no vectors exist and supports a memory-type filter.
"""

from __future__ import annotations

from app.core.config import Settings
from app.database.models import DEFAULT_PROJECT_NAME
from app.database.repositories import (
    MemoryRepository,
    PersonRepository,
    ProjectRepository,
)
from app.schemas.voice import VoiceStatusOut
from app.services.retrieval_service import RetrievalService
from app.services.voice_service import VoiceService


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------


def test_voice_status_disabled_by_default(app, client):
    response = client.get("/voice/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["stt"]["id"]
    assert body["tts"]["id"]
    assert body["message"]


def test_voice_service_respects_settings():
    settings = Settings(
        voice_enabled=True,
        voice_stt_provider="none",
        voice_tts_provider="none",
        openai_api_key="",
        openrouter_api_key="",
    )
    status = VoiceService(settings).status()
    assert isinstance(status, VoiceStatusOut)
    assert status.enabled is False
    assert status.stt.available is False
    assert status.tts.available is False


# ---------------------------------------------------------------------------
# Hybrid retrieval
# ---------------------------------------------------------------------------


def test_retrieval_lexical_fallback_when_no_vectors(app, db):
    """Fresh memories without any embeddings are still findable lexically."""
    context = app.state.context
    project = ProjectRepository(db).find_default()
    person = PersonRepository(db).create("Ava", project_id=project.id)
    MemoryRepository(db).create(
        person_id=person.id,
        content="Ava prefers hiking in the mountains over the beach.",
        memory_type="PREFERENCE",
        project_id=project.id,
        confidence=0.9,
    )
    db.commit()
    assert context.embeddings.memory_count() == 0  # nothing embedded yet

    retrieval = RetrievalService(context.embeddings, context.vector_store)
    hits = retrieval.retrieve(db, "where does Ava like to hike?", person_id=person.id, limit=3)
    assert hits
    assert hits[0].memory.content.startswith("Ava prefers hiking")
    assert hits[0].similarity > 0


def test_retrieval_memory_type_filter(app, db):
    context = app.state.context
    project = ProjectRepository(db).find_default()
    person = PersonRepository(db).create("Ben", project_id=project.id)
    pref = MemoryRepository(db).create(
        person_id=person.id, content="Ben prefers tea over coffee.", memory_type="PREFERENCE",
        project_id=project.id, confidence=0.9,
    )
    MemoryRepository(db).create(
        person_id=person.id, content="Ben goes to the gym Tuesdays.", memory_type="HABIT",
        project_id=project.id, confidence=0.9,
    )
    db.commit()
    context.embeddings.ensure_memory_embeddings(db, [pref])
    context.embeddings.ensure_memory_embeddings(db, [MemoryRepository(db).get(pref.id)])  # idempotent
    # ensure the HABIT memory is embedded too
    for memory in MemoryRepository(db).list_active(person_id=person.id):
        context.embeddings.ensure_memory_embedding(db, memory)

    retrieval = RetrievalService(context.embeddings, context.vector_store)
    # The HABIT memory matches this question lexically, but the PREFERENCE
    # filter must keep it out of the results.
    filtered = retrieval.retrieve(
        db, "Tuesdays at the gym", person_id=person.id, memory_type="PREFERENCE", limit=3
    )
    assert not filtered
    unrestricted = retrieval.retrieve(
        db, "Tuesdays at the gym", person_id=person.id, limit=3
    )
    assert [h.memory.id for h in unrestricted] == [pref.id] or any(
        h.memory.memory_type == "HABIT" for h in unrestricted
    )