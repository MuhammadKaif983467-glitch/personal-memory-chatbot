"""Tests for the ChromaDB vector store backend.

These run only when the optional ``chromadb`` package is importable (it is a
venv dependency). Chroma is exercised with a temporary persistence directory,
so the tests stay hermetic - no network, no API keys.

Coverage: store initialization, insert / upsert, similarity retrieval,
metadata filtering, delete, id listing, dimension reporting, failure handling
when chromadb is missing, and a full store-migration via EmbeddingService.
"""

from __future__ import annotations

import pytest

pytest.importorskip("chromadb")

from fastapi.testclient import TestClient  # noqa: E402

from app.ai.providers.mock_provider import MOCK_EMBEDDING_DIM, MockProvider  # noqa: E402
from app.core.exceptions import ProviderError  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402
from app.vectorstore.chroma_store import ChromaVectorStore  # noqa: E402


@pytest.fixture()
def chroma_store(tmp_path):
    return ChromaVectorStore(str(tmp_path / "chroma"))


def _seed_dataset(app, db):
    from app.services.dataset_import_service import DatasetImportService

    context = app.state.context
    dataset = {
        "dataset_name": "Chroma Mig Test",
        "version": "1.0",
        "participants": [{"name": "Ali", "role": "Friend"}],
        "conversation": {"conversation_id": "c1", "title": "t", "source": "chroma_test"},
        "designed_memory_facts": {
            "ali": [["preference", "Ali prefers coffee."], ["fact", "Ali plays guitar."]]
        },
        "intentional_corrections": [],
        "messages": [
            {
                "message_id": 1,
                "sender": "Ali",
                "timestamp": "2026-01-01T10:00:00",
                "content": "I like coffee.",
                "message_type": "text",
            }
        ],
    }
    DatasetImportService(db, context.settings, context.embeddings).import_dataset(
        dataset, consent_confirmed=True
    )


# ---- initialization & failure handling ----

def test_chroma_store_initializes_empty(chroma_store):
    assert chroma_store.name == "chroma"
    assert chroma_store.health() is True
    assert chroma_store.count() == 0
    assert chroma_store.dimension() is None
    assert chroma_store.list_ids() == []


def test_chroma_store_init_fails_loudly_when_chromadb_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "builtins.__import__",
        lambda name, *args, **kwargs: (_ for _ in ()).throw(
            ImportError("chromadb is not installed")
        )
        if name == "chromadb"
        else __import__(name, *args, **kwargs),
    )
    with pytest.raises(ProviderError) as exc:
        ChromaVectorStore(str(tmp_path / "chroma_no_dep"))
    assert "chromadb is not installed" in str(exc.value)


# ---- upsert / retrieval / delete ----

def test_chroma_upsert_query_delete_and_filter(chroma_store):
    ids = ["mem-1", "mem-2", "mem-3"]
    chroma_store.upsert(
        ids=ids,
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        metadatas=[
            {"memory_id": "1", "person_id": "p1"},
            {"memory_id": "2", "person_id": "p2"},
            {"memory_id": "3", "person_id": "p1"},
        ],
        documents=["first", "second", "third"],
    )
    assert chroma_store.count() == 3
    assert sorted(chroma_store.list_ids()) == sorted(ids)
    assert chroma_store.dimension() == 3

    hits = chroma_store.query([1.0, 0.0, 0.0], n_results=3)
    assert hits[0].id == "mem-1"
    assert hits[0].memory_id == 1
    assert hits[0].similarity == pytest.approx(1.0)
    assert {h.id for h in hits} == set(ids)

    filtered = chroma_store.query([1.0, 0.0, 0.0], n_results=3, where={"person_id": "p1"})
    assert {h.id for h in filtered} == {"mem-1", "mem-3"}
    assert all(h.metadata["person_id"] == "p1" for h in filtered)

    chroma_store.delete(["mem-2"])
    assert chroma_store.count() == 2
    assert "mem-2" not in chroma_store.list_ids()


def test_chroma_upsert_is_idempotent(chroma_store):
    metadata = {"memory_id": "7", "person_id": "p9"}
    chroma_store.upsert(["mem-7"], [[0.1, 0.2, 0.3]], [metadata], ["doc"])
    chroma_store.upsert(["mem-7"], [[0.1, 0.2, 0.3]], [metadata], ["doc"])
    assert chroma_store.count() == 1
    assert chroma_store.list_ids() == ["mem-7"]


# ---- migration via EmbeddingService ----

def test_chroma_migration_embeds_active_memories_cleanly(app, db, tmp_path):
    _seed_dataset(app, db)
    from app.database.repositories import EmbeddingRecordRepository, MemoryRepository

    active = MemoryRepository(db).list_active()
    assert active

    store = ChromaVectorStore(str(tmp_path / "chroma_mig"))
    probe = EmbeddingService(MockProvider(), store)

    migrated = probe.ensure_memory_embeddings(db, active, chunk_size=2)
    assert migrated == len(active)

    # every active memory has a vector, dimension matches, bookkeeping agrees
    assert store.count() == len(active)
    assert probe.memory_count() == len(active)
    assert store.dimension() == MOCK_EMBEDDING_DIM
    assert probe.verify_compatible(db) == []

    records = {r.vector_id for r in EmbeddingRecordRepository(db).list_all()}
    assert set(store.list_ids()) == records  # no orphan vectors, none missing

    # a re-run is idempotent: re-embedded, but no duplicate vectors
    again = probe.ensure_memory_embeddings(db, active, chunk_size=2)
    assert again == len(active)
    assert store.count() == len(active)
    assert probe.verify_compatible(db) == []

    # retrieval finds the seeded memories again from chroma
    hits = store.query(MockProvider().embed(["coffee preference"])[0], n_results=2)
    assert hits, "expected chroma retrieval to find seeded memories"
    assert hits[0].metadata["person_id"] is not None


def test_chroma_compatibility_flags_model_and_dimension_mismatch(app, db, tmp_path, monkeypatch):
    from app.ai import openrouter_provider as orp
    from app.ai.openrouter_provider import OpenRouterProvider
    from app.core.config import Settings

    from types import SimpleNamespace

    class _FakeEmbeddings:
        def create(self, **kwargs):
            count = len(kwargs.get("input", [])) or 1
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1] * 1536) for _ in range(count)]
            )

    class _FakeClient:
        def __init__(self, **kwargs):
            self.embeddings = _FakeEmbeddings()

    monkeypatch.setattr(orp.openai, "OpenAI", lambda **kwargs: _FakeClient())

    from app.database.repositories import MemoryRepository

    _seed_dataset(app, db)
    active = MemoryRepository(db).list_active()
    store = ChromaVectorStore(str(tmp_path / "chroma_mig2"))
    probe = EmbeddingService(MockProvider(), store)
    probe.ensure_memory_embeddings(db, active, chunk_size=2)
    assert probe.verify_compatible(db) == []

    # A different provider/model produces a flagged incompatibility.
    settings = Settings(
        ai_provider="openrouter",
        openrouter_api_key="sk-or-test-key-0000000000000000",
        openrouter_chat_model="openai/gpt-4o-mini",
        openrouter_embedding_model="openai/text-embedding-3-small",
        openrouter_embedding_dimensions=1536,
    )
    openrouter = OpenRouterProvider(settings)
    mismatched = EmbeddingService(openrouter, store)
    problems = mismatched.verify_compatible(db)
    assert problems, "expected a model/dimension mismatch to be reported"
    assert "1536" in " ".join(problems)
    with pytest.raises(ProviderError):
        mismatched.check_embedding_compatible(db)

    # Chroma locks a collection to its first dimension, so re-embedding the
    # same collection at a different width fails loudly instead of corrupting it.
    with pytest.raises(Exception) as excinfo:
        mismatched.ensure_memory_embeddings(db, active, chunk_size=2)
    assert "dimension" in str(excinfo.value).lower()
    assert store.count() == len(active)  # failed job left the store untouched

    # A converging migration needs a fresh collection at the new dimension.
    fresh = ChromaVectorStore(str(tmp_path / "chroma_mig3"))
    migrated = EmbeddingService(openrouter, fresh)
    assert migrated.ensure_memory_embeddings(db, active, chunk_size=2) == len(active)
    assert fresh.dimension() == 1536
    assert migrated.verify_compatible(db) == []