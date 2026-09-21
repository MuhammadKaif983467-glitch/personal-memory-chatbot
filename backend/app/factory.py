"""Application factory (side-effect free).

Constructing an app builds the database, vector store and AI provider. main.py
re-exports the default instance for uvicorn; tests import ``create_app`` here
with isolated settings so they never touch the development database.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.factory import get_provider
from app.api import chat as chat_router
from app.api import import_export as import_export_router
from app.api import memories as memories_router
from app.api import people as people_router
from app.api import projects as projects_router
from app.api import search as search_router
from app.api import settings as settings_router
from app.api import voice as voice_router
from app.api.deps import AppContext
from app.core.config import Settings, get_settings
from app.core.exceptions import ChatbotError
from app.core.logging import get_logger, setup_logging
from app.core.metrics import Metrics
from app.core.security import safe_error_message
from app.database.database import Database
from app.database.repositories import StatsRepository
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.vectorstore.factory import get_vector_store

logger = get_logger("main")


def create_app(settings_override: Optional[dict] = None) -> FastAPI:
    settings: Settings = get_settings(settings_override) if settings_override else Settings()
    setup_logging(settings.log_level)
    settings.ensure_dirs()

    db = Database(settings.database_url)
    db.init()
    provider = get_provider(settings)
    vector_store = get_vector_store(settings, db)
    embeddings = EmbeddingService(provider, vector_store)
    metrics = Metrics()
    context = AppContext(
        settings=settings,
        db=db,
        provider=provider,
        vector_store=vector_store,
        embeddings=embeddings,
        metrics=metrics,
    )
    context.chat_service = ChatService(settings, provider, embeddings, vector_store, metrics)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="A private chatbot that learns from imported conversation history.",
    )
    app.state.context = context

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router.router)
    app.include_router(people_router.router)
    app.include_router(memories_router.router)
    app.include_router(import_export_router.router)
    app.include_router(projects_router.router)
    app.include_router(search_router.router)
    app.include_router(settings_router.router)
    app.include_router(voice_router.router)

    @app.exception_handler(ChatbotError)
    async def chatbot_error_handler(request: Request, exc: ChatbotError) -> JSONResponse:
        logger.warning("Handled error %s: %s", exc.code, safe_error_message(exc.message))
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.to_dict()})

    @app.get("/health")
    def health(request: Request):
        context_: AppContext = request.app.state.context
        with context_.db.session() as session:
            counts = StatsRepository(session).snapshot()
            embedding_problems = context_.embeddings.verify_compatible(session)
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "provider": provider.name,
            "provider_auth_configured": provider.configured,
            "chat_auth_configured": getattr(provider, "chat_key_configured", provider.configured),
            "embedding_auth_configured": getattr(provider, "embedding_key_configured", provider.configured),
            "tts_configured": provider.name == "openrouter" and bool(settings.openrouter_tts_model.strip()),
            "chat_model": provider.chat_model_name,
            "embedding_model": provider.embedding_model_name,
            "embedding_compatible": not embedding_problems,
            "embedding_problems": embedding_problems,
            "vector_store": vector_store.name,
            "vector_count": vector_store.count(),
            "counts": counts,
            "counters": context_.metrics.snapshot(),
        }

    logger.info(
        "%s v%s started. provider=%s vector_store=%s db=%s",
        settings.app_name, settings.app_version, provider.name, vector_store.name, settings.database_url,
    )
    with db.session() as session:
        embedding_problems = embeddings.verify_compatible(session)
    if embedding_problems:
        logger.warning(
            "Embedding compatibility check reported issues: %s",
            " | ".join(embedding_problems),
        )
    else:
        logger.info(
            "Embedding compatibility OK (model=%s vectors=%d).",
            embeddings.provider.embedding_model, vector_store.count(),
        )
    return app