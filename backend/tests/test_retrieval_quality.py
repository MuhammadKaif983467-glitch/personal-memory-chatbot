"""Retrieval-quality coverage (Phase 13).

Answers a question must be honest about how much evidence exists. These tests
pin the six quality behaviours of the offline pipeline (deterministic
MockProvider + SimpleVectorStore, no network):

  * unrelated queries retrieve nothing and report LOW confidence,
  * ambiguous queries surface several distinct candidate memories,
  * a corrected (superseded) memory is never served as current fact,
  * retrieval is scoped to the asked person,
  * blank queries retrieve nothing,
  * low-confidence memories are not presented as fact.
"""

from __future__ import annotations

from app.database.repositories import MemoryRepository, PersonRepository
from app.services.confidence_service import interpret
from app.services.memory_service import MemoryService
from app.services.retrieval_service import RetrievalService


def _retrieval(app) -> RetrievalService:
    return RetrievalService(
        app.state.context.embeddings,
        app.state.context.vector_store,
        min_confidence=0.5,
        default_limit=5,
    )


def _seed_person(db, name: str):
    person = PersonRepository(db).create(name)
    db.commit()
    return person


def _seed_memory(
    db,
    app,
    person_id: int,
    content: str,
    memory_type: str = "FACT",
    confidence: float = 0.9,
    importance: float = 0.6,
):
    memory = MemoryRepository(db).create(
        person_id=person_id,
        content=content,
        memory_type=memory_type,
        confidence=confidence,
        importance=importance,
    )
    db.commit()
    app.state.context.embeddings.ensure_memory_embedding(db, memory)
    return memory


def test_unrelated_question_retrieves_nothing_and_is_low(db, app):
    person = _seed_person(db, "Ali")
    _seed_memory(db, app, person.id, "Ali likes cricket on the weekend")

    result = interpret(_retrieval(app).retrieve(db, "quantum chromodynamics theory", person_id=person.id))
    assert result.level == "LOW"
    assert result.score < 0.42
    assert result.signals.get("reason") == "no_memories_retrieved"


def test_ambiguous_question_returns_multiple_distinct_memories(db, app):
    person = _seed_person(db, "Ali")
    first = _seed_memory(db, app, person.id, "favourite sport cricket", memory_type="INTEREST")
    second = _seed_memory(db, app, person.id, "favourite sport football", memory_type="INTEREST")
    third = _seed_memory(db, app, person.id, "favourite sport tennis", memory_type="INTEREST")

    hits = _retrieval(app).retrieve(db, "what is his favourite sport", person_id=person.id)
    ids = [h.memory.id for h in hits]
    assert len(ids) == len(set(ids))  # no duplicate memory
    assert len(hits) >= 2
    assert first.id in ids
    assert second.id in ids
    assert third.id in ids

    result = interpret(hits)
    assert result.level != "LOW"  # solid shared-topic evidence


def test_corrected_memory_is_never_retrieved(db, app):
    person = _seed_person(db, "Ali")
    original = _seed_memory(db, app, person.id, "Ali lives in Lahore", memory_type="FACT")

    replacement = MemoryService(db).correct(
        original.id, "Ali lives in Karachi", app.state.context.embeddings
    )

    hits = _retrieval(app).retrieve(db, "where does Ali live", person_id=person.id)
    ids = [h.memory.id for h in hits]
    assert replacement.id in ids
    assert original.id not in ids  # superseded fact must not be served


def test_person_specific_evidence_is_scoped(db, app):
    ali = _seed_person(db, "Ali")
    zain = _seed_person(db, "Zain")
    _seed_memory(db, app, ali.id, "Ali prefers green tea", memory_type="PREFERENCE")
    _seed_memory(db, app, zain.id, "Ali prefers green tea", memory_type="PREFERENCE")

    for person_id in (ali.id, zain.id):
        hits = _retrieval(app).retrieve(
            db, "does Ali prefer green tea", person_id=person_id
        )
        assert hits, f"no evidence retrieved for person {person_id}"
        assert all(h.memory.person_id == person_id for h in hits)


def test_blank_question_retrieves_nothing(db, app):
    person = _seed_person(db, "Ali")
    _seed_memory(db, app, person.id, "Ali likes cricket")

    service = _retrieval(app)
    assert service.retrieve(db, "", person_id=person.id) == []
    assert service.retrieve(db, "   ", person_id=person.id) == []

    result = interpret([])
    assert result.level == "LOW"
    assert result.signals.get("reason") == "no_memories_retrieved"


def test_low_confidence_memory_is_not_presented_as_fact(db, app):
    person = _seed_person(db, "Ali")
    _seed_memory(db, app, person.id, "Ali may like chess", memory_type="OPINION", confidence=0.2)

    hits = _retrieval(app).retrieve(db, "what does Ali like", person_id=person.id)
    assert hits == []  # strong lexical match, but the memory is not reliable

    result = interpret(hits)
    assert result.level == "LOW"