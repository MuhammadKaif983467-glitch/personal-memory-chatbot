"""Vector store factory with automatic fallback.

Resolution order:
  simple  -> local SQLite + numpy store (always works)
  chroma  -> ChromaDB persistent store (needs ``pip install chromadb``)
  auto    -> chroma if importable, otherwise simple
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.database.database import Database
from app.vectorstore.base import VectorStore

logger = logging.getLogger("pmc.vectorstore")


def get_vector_store(settings: Settings, db: Database) -> VectorStore:
    mode = settings.vector_store or "auto"
    if mode == "simple":
        from app.vectorstore.simple_store import SimpleVectorStore

        return SimpleVectorStore(db)

    if mode == "chroma":
        from app.vectorstore.chroma_store import ChromaVectorStore

        return ChromaVectorStore(settings.vector_db_path)

    if mode == "auto":
        try:
            from app.vectorstore.chroma_store import ChromaVectorStore

            return ChromaVectorStore(settings.vector_db_path)
        except Exception as exc:  # chroma missing or broken
            logger.warning("ChromaDB unavailable (%s); using local SimpleVectorStore.", exc)
            from app.vectorstore.simple_store import SimpleVectorStore

            return SimpleVectorStore(db)

    raise ValueError(f"Unknown vector_store setting: {mode!r}")