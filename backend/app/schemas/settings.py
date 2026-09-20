"""Non-secret application settings exposed to the UI.

Deliberately excludes every API key. The only key-related values are the
boolean ``api_key_configured`` and the derived ``auth_status`` string. Model
names come from the active provider so the UI shows exactly what is in use,
never a raw credential.
"""

from __future__ import annotations

from pydantic import BaseModel


class SettingsOut(BaseModel):
    app_name: str
    app_version: str
    provider: str
    provider_mode: str
    api_key_configured: bool
    auth_status: str  # configured | not_configured | unavailable
    chat_key_configured: bool = False
    embedding_key_configured: bool = False
    split_keys_in_use: bool = False
    tts_configured: bool = False
    chat_model: str
    embedding_model: str
    embedding_compatible: bool
    vector_store: str
    show_memory_sources: bool
    consent_required: bool
    analyze_on_import: bool
    memory_min_confidence: float
    retrieval_limit: int
    context_budget_chars: int
    recent_conversation_messages: int
    memory_mode: str = "auto"