"""Dependency injection wiring.

All shared singletons live in :class:`AppContext`, attached to ``app.state``
so routers stay thin and tests can swap providers/stores/databases easily.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.core.config import Settings
from app.core.metrics import Metrics
from app.database.database import Database
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.vectorstore.base import VectorStore


@dataclass
class AppContext:
    settings: Settings
    db: Database
    provider: AIProvider
    vector_store: VectorStore
    embeddings: EmbeddingService
    metrics: Metrics
    chat_service: Optional[ChatService] = None


def get_context(request: Request) -> AppContext:
    return request.app.state.context


def get_settings(request: Request) -> Settings:
    context: AppContext = request.app.state.context
    return context.settings


def get_db(request: Request) -> Iterator[Session]:
    context: AppContext = request.app.state.context
    session = context.db.session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()