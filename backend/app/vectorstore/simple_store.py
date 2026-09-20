"""Local, zero-dependency vector store.

Persistence: a ``simple_vector_entries`` table in the same SQLite database,
search: numpy cosine similarity. Perfectly adequate for a personal-scale
project and keeps tests hermetic. ChromaDB remains a drop-in alternative
through the same interface.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Sequence

import numpy as np
from sqlalchemy import Column, DateTime, Integer, String, Text, text
from sqlalchemy.orm import declarative_base

from app.database.database import Database
from app.vectorstore.base import QueryHit, VectorStore

_SimpleBase = declarative_base()


class SimpleVectorEntry(_SimpleBase):
    __tablename__ = "simple_vector_entries"

    id = Column(String(100), primary_key=True)          # vector id
    memory_id = Column(Integer, nullable=False, index=True)
    model = Column(String(100), default="")
    embedding = Column(Text, default="[]")              # JSON list of floats
    metadata_json = Column(Text, default="{}")          # JSON dict
    document = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SimpleVectorStore(VectorStore):
    name = "simple"

    def __init__(self, db: Database) -> None:
        _SimpleBase.metadata.create_all(db.engine)
        self._db = db

    def upsert(
        self,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict],
        documents: Sequence[str],
    ) -> None:
        with self._db.session() as session:
            for vector_id, embedding, metadata, document in zip(ids, embeddings, metadatas, documents):
                entry = session.get(SimpleVectorEntry, vector_id)
                if entry is None:
                    entry = SimpleVectorEntry(id=vector_id)
                    session.add(entry)
                entry.memory_id = int(metadata.get("memory_id", 0))
                entry.model = metadata.get("model", "")
                entry.embedding = json.dumps([float(x) for x in embedding])
                entry.metadata_json = json.dumps(metadata, default=str)
                entry.document = document or ""
            session.commit()

    def query(
        self,
        embedding: Sequence[float],
        n_results: int,
        where: Optional[dict] = None,
    ) -> Sequence[QueryHit]:
        query_vector = np.asarray(embedding, dtype=np.float32)
        norm_q = float(np.linalg.norm(query_vector))
        if norm_q == 0:
            return []
        query_vector = query_vector / norm_q

        with self._db.session() as session:
            rows = session.query(SimpleVectorEntry).all()

        hits: list[QueryHit] = []
        for row in rows:
            metadata = json.loads(row.metadata_json or "{}")
            if where:
                matched = True
                for key, value in where.items():
                    if metadata.get(key) != value:
                        matched = False
                        break
                if not matched:
                    continue
            vector = np.asarray(json.loads(row.embedding or "[]"), dtype=np.float32)
            norm_v = float(np.linalg.norm(vector))
            if norm_v == 0:
                continue
            similarity = float(np.dot(query_vector, vector / norm_v))
            hits.append(
                QueryHit(
                    id=row.id,
                    memory_id=row.memory_id,
                    similarity=similarity,
                    metadata=metadata,
                    document=row.document or "",
                )
            )

        hits.sort(key=lambda h: h.similarity, reverse=True)
        return hits[:n_results]

    def delete(self, ids: Sequence[str], session=None) -> None:
        if session is not None:
            for vector_id in ids:
                entry = session.get(SimpleVectorEntry, vector_id)
                if entry is not None:
                    session.delete(entry)
        else:
            with self._db.session() as session:
                for vector_id in ids:
                    entry = session.get(SimpleVectorEntry, vector_id)
                    if entry is not None:
                        session.delete(entry)
                session.commit()

    def count(self) -> int:
        with self._db.session() as session:
            return int(session.query(SimpleVectorEntry).count())

    def list_ids(self) -> Sequence[str]:
        with self._db.session() as session:
            return [row[0] for row in session.query(SimpleVectorEntry.id).all()]

    def dimension(self) -> Optional[int]:
        with self._db.session() as session:
            row = session.query(SimpleVectorEntry).first()
        if row is None:
            return None
        try:
            return len(json.loads(row.embedding or "[]"))
        except Exception:
            return None

    def health(self) -> bool:
        try:
            with self._db.session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False