"""Vector store abstraction.

Different backends (ChromaDB, local SQLite+numpy) implement this interface so
retrieval does not depend on a concrete database.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass
class QueryHit:
    id: str
    memory_id: int
    similarity: float  # 1.0 = perfect match
    metadata: dict = field(default_factory=dict)
    document: str = ""


class VectorStore(ABC):
    name: str = "base"

    @abstractmethod
    def upsert(
        self,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict],
        documents: Sequence[str],
    ) -> None:
        """Insert or update vectors (idempotent per id)."""

    @abstractmethod
    def query(
        self,
        embedding: Sequence[float],
        n_results: int,
        where: Optional[dict] = None,
    ) -> Sequence[QueryHit]:
        """Return the closest vectors, sorted by similarity desc."""

    @abstractmethod
    def delete(self, ids: Sequence[str], session=None) -> None:
        """Delete vectors by id (missing ids are ignored).

        If `session` is provided, the deletion is performed within that session
        instead of opening a new one. This is required when the caller already
        holds an open transaction (e.g. during project deletion).
        """

    @abstractmethod
    def count(self) -> int:
        ...

    def dimension(self) -> Optional[int]:
        """Width of the stored vectors, or None when nothing is stored."""
        return None

    def list_ids(self) -> Sequence[str]:
        """All stored vector ids (used for orphan detection).

        Backends that cannot enumerate ids should inherit this and raise
        ``NotImplementedError``; callers treat that as "not supported".
        """
        raise NotImplementedError

    @abstractmethod
    def health(self) -> bool:
        """True if the backend is reachable."""