# Architecture

Technical architecture of the Personal Memory Chatbot v1.0.0.

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite + TypeScript)                        │
│  http://localhost:5173                                       │
│  Pages: Chat · Memories · People · Import · Settings         │
└──────────────────────┬───────────────────────────────────────┘
                       │ REST / JSON (CORS)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Backend API (FastAPI + Uvicorn)                             │
│  http://localhost:8000                                       │
│  Routers: chat · memories · people · projects ·              │
│           import_export · search · settings · voice           │
└──────────────────────┬───────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────────┐
         ▼             ▼                 ▼
   ┌───────────┐ ┌───────────┐  ┌──────────────────┐
   │ Services  │ │ AI Provider│  │ Vector Store     │
   │           │ │ (OpenRouter)│  │ (SQLite + numpy) │
   └─────┬─────┘ └───────────┘  └──────────────────┘
         │
         ▼
   ┌───────────────────┐
   │ SQLite Database   │
   │ (authoritative)   │
   └───────────────────┘
```

## Layers

### Frontend

React 18 single-page application built with Vite 5 and TypeScript. The UI connects directly to the backend API at `http://localhost:8000` (configurable via `VITE_API_URL`). No server-side rendering.

**Pages:**
- **Chat** — conversation rail, message bubbles with confidence badges, typing indicator, auto-growing composer, debug/retrieval panel
- **Memories** — timeline view, filter by type/status/search, version history, manual add/edit/correct/delete
- **People** — profile cards, structured profiles, writing style analysis, merge duplicates
- **Import** — format tabs (JSON/CSV/TXT/ZIP), preview step, progress bar, consent confirmation
- **Settings** — backend health status, voice status, model configuration display

### API Layer

FastAPI application factory pattern (`backend/app/factory.py`). The app instance is created at startup, assembling the database, vector store, AI provider, and services into an `AppContext` object attached to `app.state`.

**Routers:**
- `/chat` — POST, grounded Q&A with memory retrieval and current-conversation learning
- `/memories` — CRUD, search, correction, version history
- `/people` — list, profile, style analysis, merge
- `/projects` — CRUD, project-scoped resources
- `/import` — JSON, CSV, TXT, ZIP import with preview
- `/search` — keyword memory search
- `/settings` — configuration status (no secrets)
- `/voice` — capability/status only
- `/export` — people, conversations, messages, memories (JSON)
- `/health` — provider status, embedding compatibility, counts

### Services

Business logic layer. Services are stateless and receive dependencies via constructor injection.

| Service | Responsibility |
|---------|---------------|
| `ChatService` | Orchestrates retrieval → confidence → provider → learning |
| `MemoryService` | CRUD, correction, versioning, search |
| `RetrievalService` | Embed question → query vector store → rank results |
| `EmbeddingService` | Generate/store/remove embeddings, verify compatibility |
| `ConfidenceService` | Score and level-rank memory confidence |
| `ContextService` | Build retrieval context within token budget |
| `ImportService` | Parse, clean, and store imported conversations |
| `ProfileService` | Rule-based person profile extraction |
| `StyleService` | Writing style analysis |
| `ProjectService` | Project CRUD with cascade deletes |
| `AnalyticsService` | Conversation statistics |
| `IdentityService` | Person identity resolution and merge |
| `VoiceService` | STT/TTS capability status |

### AI Provider

Abstraction layer (`backend/app/ai/`) with a base interface and concrete implementations:

- **OpenRouter** (default) — chat and embedding via OpenRouter API, supports model fallback chains and split-key authentication
- **OpenAI** — direct OpenAI API (optional fallback)
- **Mock** — deterministic fake provider (tests)
- **Local** — offline heuristic provider (no API key needed)

The provider is selected by `AI_PROVIDER` environment variable. OpenRouter is the default live provider.

### Vector Store

Pluggable vector storage (`backend/app/vectorstore/`):

- **Simple** (default) — SQLite + numpy cosine similarity. Zero external dependencies.
- **ChromaDB** (optional) — persistent ChromaDB collection. Requires `pip install chromadb`.

One vector per active memory, paired with an `embedding_records` row (model + checksum) for deduplication and migration tracking.

### SQLite Database

Authoritative relational store. All data lives here. The vector store is a derived index.

## Data Model

```
projects
  └─ persons (project_id)
       ├─ person_profiles (1:1)
       ├─ writing_styles (1:1)
       ├─ conversations (person_id)
       │    └─ messages (conversation_id)
       │         └─ memories (source_message_id)
       │              ├─ memory_versions (memory_id, append-only)
       │              └─ embedding_records (memory_id, 1:1)
       └─ memories (person_id)
```

### Key Tables

| Table | Purpose |
|-------|---------|
| `projects` | Workspaces that scope all data |
| `persons` | People the chatbot knows about, with participant roles (ME/OTHER) |
| `conversations` | Chat sessions, scoped to a person and project |
| `messages` | Individual messages with original + cleaned content |
| `memories` | Extracted facts/preferences/habits with confidence, status, type |
| `memory_versions` | Append-only revision history per memory |
| `person_profiles` | Structured profiles (interests, preferences, facts, topics) |
| `writing_styles` | Writing style analysis results |
| `embedding_records` | Metadata for each vector (model, checksum) |
| `simple_vector_entries` | SQLite-backed vector storage (simple mode) |

### Memory Lifecycle

```
created (ACTIVE)
  │
  ├─ edited ──────► ACTIVE (new version appended)
  ├─ corrected ───► SUPERSEDED (replacement memory created as ACTIVE)
  └─ deleted ─────► ARCHIVED (version recorded, vector removed)
```

Every mutation appends a `MemoryVersion` row with actor, status, and content snapshot. Old values are never destroyed.

## Data Flows

### Import Flow

```
User uploads file (JSON/CSV/TXT/ZIP)
  → ImportPreviewService (read-only analysis)
  → User confirms consent
  → ImportService.parse()
  → CleaningService (dedup, empty/system, spam)
  → ChunkingService (split large imports)
  → Database write (persons, conversations, messages)
  → AnalysisService (extract profiles, styles, memories)
  → EmbeddingService (vector each new memory)
```

### Chat Flow

```
User sends message
  → ChatService.learn_from_user_turn() (extract "me" statements)
  → RetrievalService.retrieve()
      → EmbeddingService.embed(question)
      → VectorStore.query(person_id, top_k)
      → Rank: similarity × recency × importance × confidence
      → Lexical fallback if no vector hits
  → ContextService.build(retrieved_memories, budget)
  → Provider.generate(prompt, context)
  → ChatResponse { reply, confidence, sources, learned }
```

### Memory Learning Flow (Current-Conversation)

```
User message: "I now prefer X over Y"
  → learn_from_user_turn()
      → Detect explicit "me" statement
      → Create NEW_MEMORY for the OTHER person
      → If conflicting active memory exists:
          → Status = SUPERSEDED
          → correction_of_id linked
          → MemoryVersion row appended
      → Return outcome: NEW_MEMORY | CORRECTION | UPDATED_MEMORY | NO_MEMORY
```

### Retrieval Flow

```
Question text
  → Embed (OpenRouter embedding model)
  → Vector store query (person-scoped, top_k)
  → Filter: confidence >= min_confidence
  → Rank: similarity × recency × importance × confidence
  → Take top N results
  → If empty: lexical OR-LIKE fallback on memory content
  → Return ranked memories with metadata
```

## Security Model

- API keys stored in `.env` only, never in source code
- `.env` is git-ignored; `.env.example` has placeholders only
- `/settings` and `/health` return boolean presence flags, never key material
- Error messages are scrubbed before surfacing to responses or logs
- Import requires explicit consent confirmation
- Prompt-injection defense: system prompt marks memories as DATA, not instructions
- Split-key authentication: KEY_1 (embeddings) and KEY_2 (chat) are isolated

## Configuration

All configuration via environment variables (loaded from `.env` by pydantic-settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `auto` | Provider selection |
| `OPENROUTER_API_KEY_1` | — | Embedding key |
| `OPENROUTER_API_KEY_2` | — | Chat key |
| `OPENROUTER_CHAT_MODEL` | `openai/gpt-4o-mini` | Chat model chain |
| `OPENROUTER_EMBEDDING_MODEL` | `openai/text-embedding-3-small` | Embedding model chain |
| `VECTOR_STORE` | `auto` | `simple` or `chroma` |
| `DATABASE_URL` | `sqlite:///data/chatbot.db` | SQLAlchemy URL |
| `RETRIEVAL_LIMIT` | `12` | Max memories per retrieval |
| `CONTEXT_BUDGET_CHARS` | `9000` | Token budget for context |
| `MEMORY_MIN_CONFIDENCE` | `0.5` | Minimum confidence threshold |
