# Configuration

Environment variable reference for the Personal Memory Chatbot.

All configuration is loaded from environment variables via pydantic-settings. Copy `.env.example` to `.env` and fill in your values.

**Never commit `.env` to version control.**

## Core

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `SHOW_MEMORY_SOURCES` | `true` | Show source citations in memory responses |
| `CONSENT_REQUIRED` | `true` | Require explicit consent for import |
| `ANALYZE_ON_IMPORT` | `true` | Run memory extraction after import |
| `APP_VERSION` | `3.2.0` | Application version |

## Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///data/chatbot.db` | SQLAlchemy database URL |
| `VECTOR_DB_PATH` | — | Custom vector store path |
| `VECTOR_STORE` | `auto` | Vector backend: `simple`, `chroma`, or `auto` |

## AI Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `openrouter` | Provider: `openrouter`, `openai`, `mock`, `local`, `auto` |

### OpenRouter

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY_1` | — | Embedding API key |
| `OPENROUTER_API_KEY_2` | — | Chat API key |
| `OPENROUTER_API_KEY` | — | Legacy fallback key (both purposes) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base URL |
| `OPENROUTER_CHAT_MODEL` | — | Comma-separated chat model fallback chain |
| `OPENROUTER_EMBEDDING_MODEL` | — | Comma-separated embedding model fallback chain |
| `OPENROUTER_EMBEDDING_DIMENSIONS` | `1536` | Expected embedding dimensions |

### OpenAI (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (when `AI_PROVIDER=openai`) |
| `CHAT_MODEL` | `gpt-4o-mini` | Chat model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |

## Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_MIN_CONFIDENCE` | `0.5` | Minimum confidence for retrieval |
| `RETRIEVAL_LIMIT` | `12` | Max memories per retrieval |
| `CONTEXT_BUDGET_CHARS` | `9000` | Character budget for context |
| `RECENT_CONVERSATION_MESSAGES` | `10` | Recent messages for context |

## CORS

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed origins (comma-separated) |

## Voice (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE_ENABLED` | `false` | Enable voice features |
| `VOICE_STT_PROVIDER` | `auto` | Speech-to-text provider |
| `VOICE_TTS_PROVIDER` | `auto` | Text-to-speech provider |
| `VOICE_STT_API_KEY` | — | STT API key |
| `VOICE_TTS_API_KEY` | — | TTS API key |
| `OPENROUTER_TTS_MODEL` | `deepgram/flux-tts:free` | TTS model descriptor |

## Split-Key Configuration

The recommended setup separates embedding and chat traffic:

```text
KEY_1 (OPENROUTER_API_KEY_1)
  → Embedding requests only

KEY_2 (OPENROUTER_API_KEY_2)
  → Chat requests only
```

This separates provider usage and allows independent rate-limit handling.

The legacy `OPENROUTER_API_KEY` is used as a fallback when either KEY_1 or KEY_2 is unset.
