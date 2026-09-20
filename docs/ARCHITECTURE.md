# Architecture

Technical architecture of the Personal Memory Chatbot v3.2.0.

## System Overview

```text
┌──────────────────────────────────────────────────────────────┐
│  Frontend (React 18 + Vite 5 + TypeScript)                   │
│  http://localhost:5173                                        │
│  Components: chat/ · memory/ · people/ · import/ · projects/ │
│              settings/ · ui/                                  │
└──────────────────────┬───────────────────────────────────────┘
                       │ REST / JSON (CORS)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Backend API (FastAPI + Uvicorn)                              │
│  http://localhost:8000                                        │
│  51 endpoints across 8 routers                               │
└──────────────────────┬───────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────────┐
         ▼             ▼                 ▼
   ┌───────────┐ ┌──────────────┐  ┌──────────────────┐
   │ Services  │ │ AI Provider  │  │ Vector Store     │
   │ (12 svc)  │ │ (OpenRouter) │  │ (SQLite + NumPy) │
   └─────┬─────┘ └──────────────┘  └──────────────────┘
         │
         ▼
   ┌───────────────────┐
   │ SQLite Database   │
   │ (authoritative)   │
   └───────────────────┘
```

## Layers

### Frontend

React 18 single-page application built with Vite 5 and TypeScript. The UI connects to the backend API at `http://localhost:8000` (configurable via `VITE_API_URL`).

**Component directories:**
- `components/chat/` — ChatShell, ConversationRail, MessageBubble, MessageList, ConversationHeader
- `components/memory/` — MemoryShell, MemoryCard, MemoryEditor, MemoryFilters, MemoryHistory
- `components/people/` — PersonShell, PersonCard, PersonProfile, WritingStyleCard
- `components/import/` — ImportShell, ImportFormatTabs, ImportInputArea, ImportPreviewTable
- `components/projects/` — ProjectSwitcher, ProjectCard, CreateProjectModal, EditProjectModal
- `components/settings/` — SettingsShell, BackendStatus, ModelConfig, DisplaySettings
- `components/ui/` — Avatar, EmptyState, ErrorBanner, Skeleton, Toast

### API Layer

FastAPI application factory pattern (`backend/app/factory.py`). The app instance is created at startup, assembling the database, vector store, AI provider, and services into an `AppContext` object attached to `app.state`.

**8 routers, 51 endpoints:**
- `/chat` — POST, grounded Q&A with memory retrieval and current-conversation learning
- `/conversations` — list, get, delete, participants
- `/messages` — paginated list, get, delete
- `/memories` — CRUD, correction, versioning, archive, restore, search
- `/people` — list, get, profile, style, analyze, merge
- `/projects` — CRUD, scoped resources (people, conversations, memories)
- `/import` — universal, JSON, CSV, TXT, ZIP, JSONL, dataset, preview
- `/export` — conversations, messages, memories, people (project-scoped)
- `/search` — unified search across messages, memories, conversations
- `/settings` — configuration status (no secrets)
- `/voice` — capability/status only
- `/health` — provider status, embedding compatibility, counts

### Services

Business logic layer. Services are stateless and receive dependencies via constructor injection.

| Service | Responsibility |
|---------|---------------|
| `ChatService` | Orchestrates retrieval → context → provider → learning |
| `MemoryService` | CRUD, correction, versioning, search |
| `RetrievalService` | Embed question → query vector store → rank results |
| `EmbeddingService` | Generate/store/remove embeddings, verify compatibility |
| `ImportService` | Parse, clean, and store imported conversations |
| `ImportEngine` | Platform detection, normalizer, orchestrator, parsers |
| `ExportService` | Project-scoped JSON export |
| `ProfileService` | Rule-based person profile extraction |
| `StyleService` | Writing style analysis |
| `ProjectService` | Project CRUD with cascade deletes |
| `IdentityService` | Person identity resolution and merge |
| `AnalyticsService` | Conversation statistics |

### Chat Subsystem

Modular chat pipeline (`backend/app/services/chat/`):

| Module | Responsibility |
|--------|---------------|
| `conversation_context.py` | Build recent conversation context |
| `memory_prompt.py` | Format retrieved memories for prompt |
| `person_identity.py` | Resolve person identity for prompt |
| `response_style.py` | Apply writing style to prompt |

### AI Provider

Abstraction layer (`backend/app/ai/`) with a base interface and concrete implementations:

- **OpenRouter** (default) — chat and embedding via OpenRouter API, model fallback chains, split-key authentication, circuit breaker (5 failures → OPEN, 60s cooldown → HALF_OPEN)
- **OpenAI** — direct OpenAI API (optional fallback)
- **Mock** — deterministic fake provider (tests)
- **Local** — offline heuristic provider (no API key needed)

### Vector Store

Pluggable vector storage (`backend/app/vectorstore/`):

- **Simple** (default) — SQLite + NumPy cosine similarity. Zero external dependencies.
- **ChromaDB** (optional) — persistent ChromaDB collection. Requires `pip install chromadb`.

## Data Model

```text
projects
  └─ persons (project_id)
       ├─ person_profiles (1:1)
       ├─ writing_styles (1:1)
       ├─ conversations (person_id)
       │    ├─ conversation_participants (conversation_id)
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
| `conversations` | Chat sessions, scoped to a person and project, with fingerprint |
| `conversation_participants` | Explicit ME/OTHER participant mapping per conversation |
| `messages` | Individual messages with person_id, message_origin, and cleaned content |
| `memories` | Extracted facts/preferences/habits with confidence, status, type |
| `memory_versions` | Append-only revision history per memory |
| `person_profiles` | Structured profiles (interests, preferences, facts, topics) |
| `writing_styles` | Writing style analysis results |
| `embedding_records` | Metadata for each vector (model, checksum) |
| `simple_vector_entries` | SQLite-backed vector storage (simple mode) |

## Data Flows

### Import Flow

```text
File upload
  → ImportEngine: inspect → detect platform → parse → normalize
  → ParticipantDetector: detect ME/OTHER from senders
  → Preview (read-only)
  → User confirms consent
  → ImportService: create persons, conversations, participants, messages
  → Fingerprint: SHA-256 dedup check
  → MemoryService: extract memories from messages
  → EmbeddingService: vector each new memory
```

### Chat Flow

```text
User sends message
  → ChatService: persist user message (message_origin=live_user)
  → RetrievalService: embed → vector search → lexical fallback → rank
  → Build bounded context (memories + recent messages + profile + style)
  → Safety rules (injection protection)
  → Provider.generate (with circuit breaker)
  → Persist assistant reply (message_origin=generated)
  → Return response with sources and confidence
```

### Memory Learning Flow

```text
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

## Security Model

- API keys stored in `.env` only, never in source code
- `.env` is git-ignored; `.env.example` has placeholders only
- `/settings` and `/health` return boolean presence flags, never key material
- Error messages are scrubbed before surfacing to responses or logs
- Import requires explicit consent confirmation
- Prompt injection defense: system prompt marks memories as DATA, not instructions
- Split-key authentication: KEY_1 (embeddings) and KEY_2 (chat) are isolated
- Project isolation across all endpoints
- Parameterized SQL queries
- React XSS escaping
