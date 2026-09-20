"""Embedding service.

Responsibilities:
  - call the configured AI provider for embeddings,
  - synchronize memory <-> vector store with an EmbeddingRecord + checksum so
    unchanged memories are never re-embedded twice,
  - attach lightweight metadata to every vector (person, conversation, source
    message, timestamp, memory type) so retrieval can filter by person.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.core.exceptions import ProviderError
from app.core.logging import get_logger, safe_snippet
from app.database.models import Message
from app.database.repositories import EmbeddingRecordRepository, MessageRepository
from app.vectorstore.base import VectorStore

logger = get_logger("embeddings")


def content_checksum(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


class EmbeddingService:
    def __init__(self, provider: AIProvider, vector_store: VectorStore) -> None:
        self.provider = provider
        self.vector_store = vector_store

    def embed_texts(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return self.provider.embed(list(texts))

    def ensure_memory_embedding(self, session: Session, memory) -> bool:
        """Create/replace the vector for a memory.

        Returns True when an embedding was created or refreshed, False when it
        was already present, unchanged and produced by the active model.

        The refresh condition also covers embedding-provider/model migrations:
        a memory whose stored vector was produced by a different embedding
        model is re-embedded with the active provider.
        """
        embeddings = EmbeddingRecordRepository(session)
        existing = embeddings.get_by_memory(memory.id)
        checksum = content_checksum(memory.content)
        active_model = self.provider.embedding_model

        if (
            existing is not None
            and existing.checksum == checksum
            and existing.model == active_model
        ):
            return False

        vector = self.embed_texts([memory.content])[0]
        metadata = self._metadata_for(session, memory)
        vector_id = self._vector_id(memory.id)

        self.vector_store.upsert(
            ids=[vector_id],
            embeddings=[vector],
            metadatas=[metadata],
            documents=[memory.content],
        )
        embeddings.upsert(
            memory_id=memory.id,
            vector_id=vector_id,
            model=active_model,
            checksum=checksum,
        )
        session.commit()
        logger.info(
            "Embedded memory id=%s type=%s model=%s checksum=%s...",
            memory.id, memory.memory_type, active_model, checksum[:8],
        )
        return True

    def remove_memory_embedding(self, session: Session, memory_id: int) -> None:
        embeddings = EmbeddingRecordRepository(session)
        record = embeddings.get_by_memory(memory_id)
        if record is None:
            return
        self.vector_store.delete([record.vector_id], session=session)
        embeddings.delete_by_memory(memory_id)
        session.commit()

    def ensure_memory_embeddings(
        self, session: Session, memories: Sequence, chunk_size: int = 20
    ) -> int:
        """Embed a batch of memories with one API request per chunk.

        The migration path: every supplied memory is (re-)embedded with the
        active provider model and its vector/record replaced. Each chunk commits
        independently so a partial run is preserved and a re-run is idempotent.

        Returns the number of embeddings created/refreshed.
        """
        if not memories:
            return 0
        embeddings = EmbeddingRecordRepository(session)
        active_model = self.provider.embedding_model
        total = 0
        for start in range(0, len(memories), chunk_size):
            chunk = list(memories[start : start + chunk_size])
            vectors = self.embed_texts([m.content for m in chunk])
            if len(vectors) != len(chunk):
                # Never silently drop memories: a short vector response would
                # orphan records and hide memories from retrieval.
                raise ProviderError(
                    "The embedding provider returned fewer vectors than requested "
                    f"({len(vectors)} for {len(chunk)} texts). Refusing to write partial embeddings.",
                    reason="invalid_model",
                    status_code=503,
                )
            ids: list[str] = []
            docs: list[str] = []
            metadatas: list[dict] = []
            records: list[tuple] = []
            for memory, vector in zip(chunk, vectors):
                checksum = content_checksum(memory.content)
                vector_id = self._vector_id(memory.id)
                ids.append(vector_id)
                docs.append(memory.content)
                metadatas.append(self._metadata_for(session, memory))
                records.append((memory.id, vector_id, active_model, checksum))
            self.vector_store.upsert(
                ids=ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=docs,
            )
            for memory_id, vector_id, model, checksum in records:
                embeddings.upsert(
                    memory_id=memory_id,
                    vector_id=vector_id,
                    model=model,
                    checksum=checksum,
                )
            session.commit()
            total += len(chunk)
            logger.info(
                "Bulk-embedded memories chunk=%s total=%s model=%s",
                len(chunk),
                total,
                active_model,
            )
        return total

    def memory_count(self) -> int:
        try:
            return self.vector_store.count()
        except Exception:
            return 0

    def verify_compatible(self, session: Session) -> list[str]:
        """Return a list of embedding-compatibility problems (empty = OK).

        Detects the failure modes that produce silently-wrong retrieval:

        * stored vectors were produced by a different embedding model, or
        * stored vector width does not match the active provider's width, or
        * vectors and their ``EmbeddingRecord`` bookkeeping disagree (an
          interrupted/partial job left an orphan vector or a record without a
          vector).

        Raised problems never contain secrets; they tell the operator to run
        the re-embedding migration (``scripts/reembed_vectors.py``).
        """
        problems: list[str] = []

        active_model = self.provider.embedding_model
        expected_dim = getattr(self.provider, "embedding_dim", None)

        records = EmbeddingRecordRepository(session).list_all()
        record_ids = {r.vector_id for r in records}
        if records:
            models = sorted({r.model for r in records})
            if any(model != active_model for model in models):
                problems.append(
                    "stored embedding model(s) "
                    f"{', '.join(models)} do not match the active provider model {active_model!r}; "
                    "run `python scripts/reembed_vectors.py` to re-embed with the active model."
                )

        stored_dim = self.vector_store.dimension()
        if stored_dim is not None and expected_dim and stored_dim != expected_dim:
            problems.append(
                f"stored vector dimension {stored_dim} does not match the active provider "
                f"dimension {expected_dim}; run `python scripts/reembed_vectors.py` to re-embed."
            )

        # Orphan detection: a vector must always be paired with its record and
        # vice versa. Not all backends can enumerate ids; those that cannot skip
        # this check silently.
        vector_ids: set[str] | None = None
        try:
            vector_ids = set(self.vector_store.list_ids())
        except (NotImplementedError, Exception):
            vector_ids = None
        if vector_ids is not None:
            orphans = vector_ids - record_ids
            missing = record_ids - vector_ids
            if orphans:
                problems.append(
                    f"{len(orphans)} stored vector(s) have no embedding record "
                    "(left by an interrupted embed job); run `python scripts/reembed_vectors.py` to repair."
                )
            if missing:
                problems.append(
                    f"{len(missing)} embedding record(s) have no stored vector "
                    "(their memory would never be retrieved); run `python scripts/reembed_vectors.py` to repair."
                )
        return problems

    def check_embedding_compatible(self, session: Session) -> None:
        """Raise a clear ProviderError when stored vectors are incompatible.

        Called at retrieval time so the application fails loudly instead of
        searching with mismatched vectors. Offline providers (``local``/``mock``)
        always pass: their hash embeddings have no provider-specific model tag.
        """
        if getattr(self.provider, "offline", False):
            return
        problems = self.verify_compatible(session)
        if problems:
            from app.core.exceptions import ProviderError

            raise ProviderError(
                "The stored embeddings are incompatible with the active AI provider. "
                + " ".join(problems),
                reason="invalid_model",
                status_code=503,
            )

    @staticmethod
    def _vector_id(memory_id: int) -> str:
        return f"mem-{memory_id}"

    def _metadata_for(self, session: Session, memory) -> dict:
        conversation_id = None
        source_timestamp = None
        if memory.source_message_id is not None:
            source: Optional[Message] = MessageRepository(session).get(memory.source_message_id)
            if source is not None:
                conversation_id = source.conversation_id
                source_timestamp = source.timestamp
        timestamp = memory.created_at or datetime.now(timezone.utc)
        return {
            "memory_id": str(memory.id),
            "project_id": str(memory.project_id or ""),
            "person_id": str(memory.person_id),
            "conversation_id": str(conversation_id or ""),
            "source_message_id": str(memory.source_message_id or ""),
            "timestamp": timestamp.isoformat(),
            "memory_type": memory.memory_type,
            "model": self.provider.embedding_model,
        }