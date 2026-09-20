# Personal Memory Chatbot

A personal-memory conversation AI that imports two-person chat history, builds persistent evidence-backed memories and communication-style profiles, and generates grounded responses with source citations.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue.svg)](https://www.typescriptlang.org/)
[![OpenRouter](https://img.shields.io/badge/AI-OpenRouter-purple.svg)](https://openrouter.ai/)
[![Tests](https://img.shields.io/badge/Backend%20Tests-260%20passed-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)
[![Version](https://img.shields.io/badge/Version-3.2.0-brightgreen.svg)](#release-history)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Testing](#testing)
- [Performance](#performance)
- [API](#api)
- [Security](#security)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Release History](#release-history)
- [License](#license)

---

## Overview

The Personal Memory Chatbot is a personal-deployment AI application that imports two-person conversation history, models explicit ME/OTHER identities, builds persistent memories with confidence scoring and full revision history, and generates responses grounded in retrieved memories and communication-style signals.

The system supports multiple import formats (WhatsApp, Telegram, Instagram, Facebook, JSON, CSV, TXT, ZIP), project-scoped data isolation, hybrid retrieval (vector + lexical), and OpenRouter provider integration with model fallback chains.

---

## Features

### Conversation

- Two-person conversation model with explicit ME/OTHER participant mapping
- Conversation participants persisted and backfilled for existing conversations
- Message ownership tracked via `person_id`
- Message origin distinguished (`live_user`, `generated`, `imported`)
- Project-scoped conversations and messages

### Memory

- Persistent memories extracted from conversation history
- Categories: facts, preferences, interests, habits, opinions
- Confidence scoring and level ranking (HIGH/MEDIUM/LOW)
- Full revision history via append-only `memory_versions` table
- Corrections create replacement memories rather than destroying history
- Source traceability — each memory linked to its source message
- Current-conversation learning from explicit "me" statements

### Import

- **Formats:** WhatsApp-compatible text, Telegram JSON, Instagram JSON, Facebook JSON, generic TXT, CSV, JSON, JSONL, ZIP
- Universal import with automatic platform detection
- Read-only preview before persistent storage
- Participant detection and identity mapping
- Fingerprint-based conversation deduplication (SHA-256)
- Message-level deduplication
- Media/system-message filtering, spam filtering
- Consent confirmation required

### AI

- OpenRouter provider with model fallback chains
- Split API keys: KEY_1 for embeddings, KEY_2 for chat
- Embedding fallback chains for model availability
- Provider circuit breaker (5 failures, 60s cooldown)
- Bounded retries (3 for chat, 10 for embeddings)
- Lexical fallback when vector retrieval produces no results
- Response grounded in memories, context, and communication style
- Prompt injection protection — imported content treated as data

### Reliability

- Exponential backoff retry with rate-limit detection
- Circuit breaker preventing cascading failures
- Frontend request cancellation via AbortController
- Paginated message retrieval for large conversations
- Stale-request epoch protection
- Idempotent conversation import via fingerprint dedup
- Typed frontend error classification (NETWORK_ERROR, PROVIDER_ERROR, RATE_LIMITED, etc.)

### Security

- API keys stored in `.env`, never committed
- `.env.example` contains placeholders only
- Health/settings endpoints expose no secrets
- Prompt injection defense — memories marked as DATA, not instructions
- Project isolation across all endpoints
- ZIP/path traversal protection on import
- SQLAlchemy parameterized queries (SQL injection prevention)
- React XSS escaping on all output
- Export endpoints scoped by `project_id`

### UI

- Premium dark UI with responsive layout
- Project creation, editing, switching
- Conversation rail with search
- Paginated message list with "Load older messages"
- Memory timeline with filters, corrections, version history
- Person profiles with writing-style analysis
- Import wizard with format tabs, preview, progress
- Settings with backend status, model config display
- Connection status (CONNECTED / DEGRADED / OFFLINE)
- Reduced-motion support

---

## Architecture

```text
Project
  → People (ME/OTHER)
    → Conversations
      → ConversationParticipants
        → Messages
          → Memories (extracted)
            → Memory Versions (history)
              → Embeddings (vector index)

User message
  → Conversation context
  → Memory retrieval (vector + lexical)
  → Person profile + writing style
  → Safety rules
  → Prompt construction
  → OpenRouter (with circuit breaker)
  → Response validation
```

**Backend:** FastAPI → Services → Repositories → SQLAlchemy → SQLite

**AI:** OpenRouter with split-key authentication, model fallback chains, and circuit breaker

**Vector Store:** SQLite + NumPy cosine similarity (default), ChromaDB (optional)

Full architecture documentation: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18, TypeScript, Vite 5 | UI, type safety, build tooling |
| Backend | Python 3.10+, FastAPI, SQLAlchemy 2.0 | API, ORM, services |
| Database | SQLite | Primary relational store |
| Vector Store | NumPy + SQLite (default) | Semantic retrieval |
| AI | OpenRouter | Provider gateway |
| Testing | pytest, TypeScript compiler | Automated verification |

---

## Quick Start

### Prerequisites

- Windows 10/11, macOS, or Linux
- Python 3.10 or newer
- Node.js 18 or newer
- npm
- Git
- OpenRouter API key(s) (for live AI responses)

### Clone

```powershell
git clone https://github.com/MuhammadKaif983467-glitch/personal-memory-chatbot.git
cd chatbot
```

### Configure

```powershell
Copy-Item .env.example .env
```

Edit `.env` and configure at minimum:

```ini
OPENROUTER_API_KEY_1=your_embedding_key
OPENROUTER_API_KEY_2=your_chat_key
```

### Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

### Frontend Setup

```powershell
cd frontend
npm install
```

### Start

```powershell
# Terminal 1 — Backend
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Or use the all-in-one script:

```powershell
.\scripts\start_all.ps1
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

---

## Configuration

All configuration via environment variables (`.env`):

```ini
AI_PROVIDER=openrouter
OPENROUTER_API_KEY_1=your_embedding_key
OPENROUTER_API_KEY_2=your_chat_key
VECTOR_STORE=simple
DATABASE_URL=
```

Full configuration reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

---

## Testing

### Backend

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

### Frontend

```powershell
cd frontend
npm run typecheck
npm run build
```

### Verified Baseline (v3.2.0)

| Check | Result |
|-------|--------|
| Backend tests | 260/260 PASS |
| Frontend typecheck | PASS |
| Frontend build | PASS (207.83 KB JS, gzip: 62.65 KB) |
| Database integrity | PASS (0 NULL person_id, 0 orphans, 0 FK violations) |
| Secret scan | PASS (no keys in source) |

Known limitations:
- Browser E2E unavailable in certification environment
- No automated backup/recovery
- Retry jitter not implemented
- Imported messages are immutable

---

## Performance

Measured certification results (v3.2.0, local SQLite, test database):

| Operation | p50 |
|-----------|-----|
| Backend startup | ~11s |
| Health endpoint | 107ms |
| Project list | 250ms |
| People list | 39ms |
| Conversation list | 14ms |
| Messages (200) | 34ms |
| Search | 44ms |
| Import (100 messages) | 184ms |

Full performance documentation: [docs/PERFORMANCE.md](docs/PERFORMANCE.md)

---

## API

The backend provides 51 REST endpoints across these areas:

| Area | Endpoints |
|------|-----------|
| Chat | `POST /chat`, `GET /conversations`, `GET /messages` |
| Import | `POST /import/universal`, `POST /import/json`, `POST /import/csv`, `POST /import/txt`, `POST /import/zip` |
| Export | `GET /export/conversations`, `GET /export/messages`, `GET /export/memories` |
| Projects | `POST /projects`, `GET /projects`, `PATCH /projects/{id}` |
| People | `GET /people`, `GET /people/{id}/profile`, `POST /people/{id}/analyze` |
| Memories | `GET /memories`, `POST /memories/{id}/correct`, `POST /memories/{id}/archive` |
| Search | `POST /search` |
| Settings | `GET /settings` |
| Health | `GET /health` |

Interactive API documentation: http://localhost:8000/docs

Full API reference: [docs/API.md](docs/API.md)

---

## Security

- API keys in `.env` only, never committed
- Health/settings endpoints expose no secrets
- Imported content treated as data, not instructions
- Project isolation across all endpoints
- Parameterized SQL queries
- React XSS escaping
- ZIP/path traversal protection

Full security documentation: [SECURITY.md](SECURITY.md)

---

## Known Limitations

- **OpenRouter rate limits** — Free-tier models have provider-specific limits. Provider failures do not represent local application failures.
- **Offline provider** — The local heuristic provider works without an API key but provides basic responses only.
- **Voice** — Architecture and status API implemented. Full STT/TTS integration is planned.
- **No browser E2E** — Automated browser testing not available in certification environment.
- **No automated backup** — Database backup is manual.
- **Retry jitter** — Exponential backoff without jitter.
- **Imported messages immutable** — No revision history for imported content.

---

## Roadmap

### Completed

- Two-person project model
- Multi-format import (WhatsApp, Telegram, Instagram, Facebook, JSON, CSV, TXT, ZIP)
- Persistent memory with confidence and revision history
- Hybrid retrieval (vector + lexical)
- Provider circuit breaker and bounded retries
- Fingerprint-based conversation deduplication
- Paginated message retrieval
- Project-scoped export
- Security regression tests

### Planned

- Browser E2E testing
- Automated backup/recovery
- Retry jitter
- Imported-message revision history
- Message virtualization
- Advanced retrieval/reranking
- Improved style matching
- Voice input/output
- Additional import formats
- Deployment support (Docker, CI/CD)
- Observability and monitoring
- Evaluation benchmarks

Full roadmap: [ROADMAP.md](ROADMAP.md)

---

## Release History

| Version | Date | Summary |
|---------|------|---------|
| v3.2.0 | 2026-09-21 | Production hardening, circuit breaker, fingerprint dedup, 260 tests |
| v1.0.0 | 2026-09-21 | Initial production release |

Full changelog: [CHANGELOG.md](CHANGELOG.md)

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Technical architecture |
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Setup instructions |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables |
| [docs/API.md](docs/API.md) | API reference |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Performance measurements |
| [docs/PRIVACY.md](docs/PRIVACY.md) | Privacy considerations |
| [SECURITY.md](SECURITY.md) | Security policy |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guide |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Code of conduct |
| [ROADMAP.md](ROADMAP.md) | Development roadmap |

---

## License

This project is licensed under the MIT License.

Copyright (c) 2026 Muhammad Kaif
