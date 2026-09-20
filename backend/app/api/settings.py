"""Read-only, secret-free settings endpoint for the UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AppContext, get_context
from app.schemas.settings import SettingsOut

router = APIRouter()


@router.get("/settings", response_model=SettingsOut)
def get_app_settings(context: AppContext = Depends(get_context)):
    """Return safe configuration. Never includes API keys or secrets."""
    settings = context.settings
    provider = context.provider

    with context.db.session() as session:
        incompatible = provider.embedding_model and not getattr(provider, "offline", False)
        problems = context.embeddings.verify_compatible(session) if incompatible else []

    auth_status = (
        "configured"
        if provider.configured
        else ("unavailable" if getattr(provider, "offline", False) else "not_configured")
    )
    return SettingsOut(
        app_name=settings.app_name,
        app_version=settings.app_version,
        provider=provider.name,
        provider_mode=settings.ai_provider,
        api_key_configured=provider.configured,
        auth_status=auth_status,
        # Split-role key status (secret-free booleans only).
        chat_key_configured=getattr(provider, "chat_key_configured", provider.configured),
        embedding_key_configured=getattr(provider, "embedding_key_configured", provider.configured),
        split_keys_in_use=settings.split_keys_in_use,
        tts_configured=provider.name == "openrouter" and bool(settings.openrouter_tts_model.strip()),
        chat_model=provider.chat_model_name or "n/a (offline provider)",
        embedding_model=provider.embedding_model_name or "hash embeddings (offline)",
        embedding_compatible=not problems,
        vector_store=context.vector_store.name,
        show_memory_sources=settings.show_memory_sources,
        consent_required=settings.consent_required,
        analyze_on_import=settings.analyze_on_import,
        memory_min_confidence=settings.memory_min_confidence,
        retrieval_limit=settings.retrieval_limit,
        context_budget_chars=settings.context_budget_chars,
        recent_conversation_messages=settings.recent_conversation_messages,
        memory_mode=settings.memory_mode,
    )