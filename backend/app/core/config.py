"""Application configuration.

Settings are loaded from environment variables and an optional ``.env`` file
(located in the project root or the ``backend`` folder). Values can be
overridden at runtime by constructing ``Settings(**overrides)`` which is how
tests inject isolated databases and fake providers.

Important: never hard-code secrets in source. API keys come from the
environment / ``.env`` file only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Path of the backend/app/core folder -> root project folder.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _sqlite_url(path: Path) -> str:
    """Return a SQLAlchemy sqlite URL for an absolute path (Windows safe)."""
    return f"sqlite:///{path.as_posix()}"


def _default_db_url() -> str:
    return _sqlite_url(PROJECT_ROOT / "data" / "chatbot.db")


def _default_dir(name: str) -> Path:
    return PROJECT_ROOT / "data" / name


def _split_model_chain(value) -> Tuple[str, ...]:
    """Split a model chain value (list or comma/newline/space separated text)."""
    if value is None:
        return ()
    raw: list[str]
    if isinstance(value, (list, tuple, set)):
        raw = [str(item) for item in value]
    else:
        raw = str(value).replace("\n", ",").split(",")
    seen: list[str] = []
    for chunk in raw:
        for part in str(chunk).split():
            part = part.strip()
            if part and part not in seen:
                seen.append(part)
    return tuple(seen)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Core ----
    app_name: str = "Personal Memory Chatbot"
    app_version: str = "3.2.0"
    log_level: str = "INFO"
    show_memory_sources: bool = True
    consent_required: bool = True
    analyze_on_import: bool = True

    # ---- Storage ----
    database_url: str = ""
    vector_db_path: str = ""
    imports_dir: str = ""
    processed_dir: str = ""
    exports_dir: str = ""
    vector_store: str = "auto"  # auto | chroma | simple

    # ---- AI ----
    # auto | openrouter | openai | mock | local
    ai_provider: str = "auto"

    # OpenRouter (default live provider)
    #
    # Key separation: OPENROUTER_API_KEY_1 is used for embedding calls,
    # OPENROUTER_API_KEY_2 for chat calls. The legacy OPENROUTER_API_KEY is a
    # fallback for both when the dedicated key for an operation is unset, so
    # existing single-key setups keep working unchanged.
    openrouter_api_key: str = ""
    openrouter_api_key_1: str = ""  # embeddings only
    openrouter_api_key_2: str = ""  # chat only
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "openai/gpt-4o-mini"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_embedding_dimensions: int = 1536
    openrouter_tts_model: str = ""  # capability-layer descriptor, never required

    # Optional ordered model fallback chains (comma/space/newline separated).
    # The provider tries every model listed; if a model is not accessible on the
    # account (or returns an unusable embedding dimension) it falls back to the
    # next one in the chain. Each chain always starts with the primary model name.
    openrouter_chat_models: Tuple[str, ...] = ()
    openrouter_embedding_models: Tuple[str, ...] = ()

    # Optional OpenAI configuration kept for provider switching (untouched by
    # the OpenRouter migration; never required when OpenRouter is active).
    openai_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # ---- Voice (Phase V architecture) ----
    # The two-person memory product never depends on voice. When enabled, STT
    # and TTS are routed through provider plugins that the user supplies their
    # own keys for. "auto" resolves to the best available plugin; otherwise a
    # concrete provider id or "none" disables that leg entirely.
    voice_enabled: bool = False
    voice_stt_provider: str = "auto"  # auto | openai-whisper | none | <custom>
    voice_tts_provider: str = "auto"  # auto | elevenlabs | local | none | <custom>
    voice_stt_api_key: str = ""
    voice_tts_api_key: str = ""

    # ---- Retrieval / context / confidence ----
    memory_min_confidence: float = 0.5
    retrieval_limit: int = 12
    context_budget_chars: int = 9000
    recent_conversation_messages: int = 10

    # ---- Memory learning mode ----
    # auto     -> new memories from current-conversation learning are stored
    #             automatically (still gated by confidence + evidence)
    # ask      -> learning produces a proposed memory that the user explicitly
    #             confirms (Save / Discard / Edit) before anything is stored
    # disabled -> no memory is learned from current chat turns
    memory_mode: str = "auto"

    # ---- Import hardening (caps, not policy) ----
    # Bounds protect the process from unbounded uploads / payloads. Importing
    # more data than these needs chunked imports instead of one giant request.
    import_max_bytes: int = 200 * 1024 * 1024  # 200 MB per upload
    import_max_messages: int = 200_000  # per import payload

    # ---- Misc ----
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Validators: empty env values fall back to sensible defaults ----

    @field_validator(
        "openai_api_key",
        "openrouter_api_key",
        "openrouter_api_key_1",
        "openrouter_api_key_2",
        mode="before",
    )
    @classmethod
    def _empty_keys(cls, value: object) -> object:
        """Treat blank/placeholder key values as unset.

        ``your_openrouter_api_key_here`` style values shipped in ``.env.example``
        must never count as a configured credential.
        """
        if value is None:
            return ""
        text = str(value).strip()
        if not text or text.casefold() in ("your_api_key_here", "your_openrouter_api_key_here", "changeme"):
            return ""
        return text

    @field_validator("openrouter_chat_models", "openrouter_embedding_models", mode="before")
    @classmethod
    def _parse_model_list(cls, value: object) -> Tuple[str, ...]:
        """Parse a model chain from a list, comma text or whitespace text."""
        return _split_model_chain(value)

    @field_validator("memory_mode", mode="before")
    @classmethod
    def _normalize_memory_mode(cls, value: object) -> object:
        mode = str(value or "").strip().casefold()
        if mode not in ("auto", "ask", "disabled"):
            return "auto"
        return mode

    @field_validator("database_url", mode="before")
    @classmethod
    def _empty_db_url(cls, value: object) -> object:
        return value if value else _default_db_url()

    @field_validator("vector_db_path", mode="before")
    @classmethod
    def _empty_vector_path(cls, value: object) -> object:
        return value if value else str(PROJECT_ROOT / "data" / "chroma")

    @field_validator("imports_dir", "processed_dir", "exports_dir", mode="before")
    @classmethod
    def _empty_dir(cls, value: object, info) -> object:
        if value:
            return value
        # info.field_name is the validated field name being filled.
        name = info.field_name.replace("_dir", "") if info.field_name else "data"
        return str(_default_dir(name))

    # ---- Helpers ----

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def chat_model_chain(self) -> Tuple[str, ...]:
        """Ordered chat models to try (primary first, then env extras).

        The primary ``OPENROUTER_CHAT_MODEL`` may itself be a comma/whitespace
        separated list; every model in it is tried in order, after which models
        listed in ``OPENROUTER_CHAT_MODELS`` are appended.
        """
        chain = list(_split_model_chain(self.openrouter_chat_model))
        for model in self.openrouter_chat_models:
            if model not in chain:
                chain.append(model)
        return tuple(chain) or ("openai/gpt-4o-mini",)

    @property
    def embedding_model_chain(self) -> Tuple[str, ...]:
        """Ordered embedding models to try (primary first, then env extras)."""
        chain = list(_split_model_chain(self.openrouter_embedding_model))
        for model in self.openrouter_embedding_models:
            if model not in chain:
                chain.append(model)
        return tuple(chain) or ("openai/text-embedding-3-small",)

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    # ---- Key separation helpers (secret values never leave via these) ----

    @property
    def openrouter_chat_api_key(self) -> str:
        """Chat key: OPENROUTER_API_KEY_2, falling back to the legacy key."""
        return self.openrouter_api_key_2 or self.openrouter_api_key

    @property
    def openrouter_embedding_api_key(self) -> str:
        """Embedding key: OPENROUTER_API_KEY_1, falling back to the legacy key."""
        return self.openrouter_api_key_1 or self.openrouter_api_key

    @property
    def chat_key_configured(self) -> bool:
        return bool(self.openrouter_chat_api_key)

    @property
    def embedding_key_configured(self) -> bool:
        return bool(self.openrouter_embedding_api_key)

    # True when the keys were configured through the dedicated split-role
    # variables AND they are distinct credentials (i.e. not the identical
    # single-key fallback).
    @property
    def split_keys_in_use(self) -> bool:
        return bool(self.openrouter_api_key_1) and bool(self.openrouter_api_key_2)

    def ensure_dirs(self) -> None:
        """Create every directory the app needs at startup."""
        for field in ("imports_dir", "processed_dir", "exports_dir"):
            Path(getattr(self, field)).mkdir(parents=True, exist_ok=True)
        Path(self.vector_db_path).mkdir(parents=True, exist_ok=True)
        db_path = self.database_url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def get_settings(overrides: Optional[dict] = None) -> Settings:
    """Return a Settings instance; used for test-time overrides."""
    if overrides:
        return Settings(**overrides)
    return Settings()
