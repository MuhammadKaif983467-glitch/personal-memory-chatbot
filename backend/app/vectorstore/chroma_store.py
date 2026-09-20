"""ChromaDB backed vector store.

Requires the optional ``chromadb`` package. When it is not installed the app
falls back to the local SimpleVectorStore (see vectorstore/simple_store.py).
"""

from __future__ import annotations

from typing import Optional, Sequence

from app.core.exceptions import ProviderError
from app.vectorstore.base import QueryHit, VectorStore

_COLLECTION_NAME = "memories"


class ChromaVectorStore(VectorStore):
    name = "chroma"

    def __init__(self, persist_path: str) -> None:
        try:
            import chromadb  # imported lazily because it is optional
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise ProviderError(
                "chromadb is not installed. Set VECTOR_STORE=simple or run "
                "`pip install chromadb`."
            ) from exc
        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection = self._client.get_or_create_collection(
            _COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    def upsert(
        self,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict],
        documents: Sequence[str],
    ) -> None:
        docs = [d or "" for d in documents]
        self._collection.upsert(
            ids=list(ids),
            embeddings=[list(e) for e in embeddings],
            metadatas=list(metadatas),
            documents=docs,
        )

    def query(
        self,
        embedding: Sequence[float],
        n_results: int,
        where: Optional[dict] = None,
    ) -> Sequence[QueryHit]:
        kwargs: dict = {"query_embeddings": [list(embedding)], "n_results": n_results}
        if where:
            kwargs["where"] = {k: str(v) for k, v in where.items()}
        result = self._collection.query(**kwargs)
        ids = result.get("ids", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or []
        metadatas = result.get("metadatas", [[]])[0] or []
        documents = result.get("documents", [[]])[0] or []
        hits: list[QueryHit] = []
        for i, doc_id in enumerate(ids):
            distance = float(distances[i]) if i < len(distances) else 1.0
            metadata = metadatas[i] if i < len(metadatas) else {}
            hits.append(
                QueryHit(
                    id=doc_id,
                    memory_id=int(metadata.get("memory_id", 0)),
                    similarity=max(0.0, 1.0 - distance),
                    metadata=metadata or {},
                    document=documents[i] if i < len(documents) else "",
                )
            )
        hits.sort(key=lambda h: h.similarity, reverse=True)
        return hits

    def delete(self, ids: Sequence[str], session=None) -> None:
        if not ids:
            return
        self._collection.delete(ids=list(ids))

    def count(self) -> int:
        return int(self._collection.count())

    def list_ids(self) -> list[str]:
        """Enumerate every stored vector id (used for orphan detection)."""
        return list(self._collection.get(include=[])["ids"])

    def dimension(self) -> int | None:
        try:
            if self._collection.count() == 0:
                return None
            fetched = self._collection.get(limit=1, include=["embeddings"])
            embeddings = fetched.get("embeddings")
            first = embeddings[0] if embeddings is not None and len(embeddings) else None
            if first is not None:
                row = list(first)
                if row:
                    return len(row)
        except Exception:
            return None
        return None

    def health(self) -> bool:
        try:
            return self._collection.count() >= 0
        except Exception:
            return False