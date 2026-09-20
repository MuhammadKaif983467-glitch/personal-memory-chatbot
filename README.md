# Personal Memory Chatbot

A privacy-conscious personal memory chatbot that imports conversations, analyzes long-term communication history, builds evidence-backed memories, and provides grounded answers using hybrid retrieval and source-aware context.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)
[![v1.0.0](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](#certification)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Screenshots](#screenshots)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Testing](#testing)
- [Certification](#certification)
- [Security](#security)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

The Personal Memory Chatbot learns about a person from their conversation history. Import WhatsApp-style chat logs, and the system automatically extracts facts, preferences, habits, and opinions — each linked to the exact message it came from. When you chat, answers are retrieved from these memories and the system tells you how confident it is.

The whole system is designed to be **personally deployable**: SQLite + a local vector store, a single Uvicorn process, and a React frontend. OpenRouter is the only external dependency when you want real AI-powered answers.

---

## Key Features

### Two-Person Project Model
- Create projects with exactly two participants: one **ME** (your side) and one **OTHER** (the person the chatbot remembers)
- All data — people, conversations, memories, vectors — is scoped to the project
- Default project protection (cannot be deleted)

### Conversation Import
- **JSON, CSV, TXT, and ZIP** format support
- **Preview step** (read-only) before anything is stored
- Automatic cleaning (duplicates, empty messages, system messages, spam)
- Consent confirmation required
- Idempotent re-imports (no duplicates)

### Persistent Memories
- Rule-based extraction of **facts, preferences, interests, habits, and opinions**
- Each memory traced to its **exact source message**
- **Confidence scoring** with HIGH / MEDIUM / LOW levels
- **Memory versioning** — full revision history for every create, edit, correction, and delete

### Corrections & Supersession
- Correct wrong memories — old value is retired (never overwritten)
- Replacement memory created and linked
- Full audit trail via `memory_versions` table

### Current-Conversation Learning
- Explicit statements ("I now prefer X over Y") are automatically remembered
- Conflicting memories are superseded with correction links
- Each reply shows what was just learned (NEW / CORRECTION / NO_MEMORY)

### Hybrid Retrieval
- **Vector similarity** search (person-scoped, cosine similarity)
- **Lexical fallback** when no vector matches (OR-LIKE search on memory content)
- Ranking by: similarity x recency x importance x confidence
- Source citation — every answer shows which memories it used

### Source & Evidence Grounding
- Every answer reports its confidence level
- Debug panel shows retrieval details (ranked memories, similarity scores)
- Memory sources panel shows exact memories used in the response

### Project Isolation
- Data for different people and conversations is fully isolated
- Cross-project queries return only relevant results
- Deletion of a project cascades vectors, embeddings, and memories

### Premium Chat UI
- Dark theme with responsive design
- Real-time backend connection status (CONNECTED / DEGRADED / OFFLINE)
- Project switcher with quick creation
- Conversation rail with history
- Animated transitions with `prefers-reduced-motion` support

### Voice Architecture
- Backend STT/TTS capability status (`/voice/status`)
- Pluggable provider architecture (disabled by default)
- Browser audio capture left to Web Speech API / MediaRecorder

### Security
- API keys from environment only — never in source code
- `.env` git-ignored; `.env.example` has placeholders only
- `/settings` and `/health` never return key material
- Prompt-injection defense: memories marked as DATA, not instructions
- Import requires explicit consent confirmation
- Error messages scrubbed before surfacing

### OpenRouter Provider
- Split-key authentication (KEY_1 for embeddings, KEY_2 for chat)
- Model fallback chains for both chat and embeddings
- Rate-limit aware with automatic retry
- Offline `local` provider for zero-key usage

---

## Screenshots

> Screenshots are planned for a future release. The application UI is a premium dark-theme interface with the following screens:

| Screen | Purpose |
|--------|---------|
| `docs/screenshots/dashboard.png` | Main chat interface with conversation rail |
| `docs/screenshots/chat.png` | Chat with grounded answer and source evidence |
| `docs/screenshots/memories.png` | Memory timeline with version history |
| `docs/screenshots/people.png` | Person profiles and writing style analysis |
| `docs/screenshots/import.png` | Import workflow with preview |
| `docs/screenshots/settings.png` | Settings with connection status |

> **Note:** Screenshots will be captured from a live running instance and added before public launch.

---

## Architecture

```
Frontend (React + Vite + TypeScript)
        │
        ▼
Backend API (FastAPI + Uvicorn)
        │
   ┌────┼────────────┐
   ▼    ▼            ▼
Services  AI Provider  Vector Store
   │     (OpenRouter)  (SQLite + numpy)
   ▼
SQLite Database
```

**Request flow:** `frontend → POST /chat → chat_service → retrieval_service (embed → query vector store → rank) → confidence_service → provider.generate(...) → structured reply + sources`

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Technology Stack

### Frontend
- **React 18** — UI framework
- **TypeScript** — Type safety
- **Vite 5** — Build tool and dev server

### Backend
- **Python 3.10+** — Runtime
- **FastAPI** — Web framework
- **SQLAlchemy 2.0** — ORM
- **Pydantic** — Data validation

### Data
- **SQLite** — Authoritative relational store
- **NumPy** — Cosine similarity for vector search
- **Optional ChromaDB** — Alternative vector store

### AI
- **OpenRouter** — Unified API for chat and embedding models
- **OpenAI-compatible API** — Standard interface
- **Embedding fallback chain** — Automatic model fallback
- **Chat fallback chain** — Graceful degradation

### Testing
- **pytest** — 174 backend tests
- **TypeScript typecheck** — Frontend type safety
- **Vite production build** — Optimized frontend bundle
- **Live E2E acceptance** — 11 end-to-end verification tests

---

## Project Structure

```
chatbot/
├── .env                    # Runtime configuration (git-ignored)
├── .env.example            # Configuration template
├── LICENSE                 # MIT License
├── README.md
├── CHANGELOG.md
├── docker-compose.yml      # Docker deployment
├── docs/
│   ├── ARCHITECTURE.md     # Technical architecture
│   ├── GITHUB_DESCRIPTION.md
│   ├── PORTFOLIO.md
│   ├── LINKEDIN_PROJECT.md
│   ├── DEMO_SCRIPT.md
│   ├── SCREENSHOT_PLAN.md
│   ├── RESUME_ENTRY.md
│   └── GITHUB_RELEASE_v1.0.0.md
├── backend/
│   ├── app/
│   │   ├── ai/             # AI provider abstraction
│   │   ├── api/            # REST endpoints
│   │   ├── core/           # Config, logging, security
│   │   ├── database/       # ORM models and repositories
│   │   ├── services/       # Business logic
│   │   ├── vectorstore/    # Vector storage backends
│   │   └── factory.py      # Application factory
│   ├── scripts/            # Dataset import, re-embedding, probes
│   ├── tests/              # 174 hermetic tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # UI components
│   │   ├── pages/          # Page views
│   │   ├── services/       # API client
│   │   └── types.ts        # TypeScript types
│   └── package.json
├── scripts/
│   ├── start_all.ps1       # Full stack startup
│   ├── start_backend.ps1   # Backend startup
│   └── start_frontend.ps1  # Frontend startup
├── tests/
│   └── .gitkeep
└── data/                   # Runtime data (git-ignored)
    ├── chatbot.db          # SQLite database
    └── imports/            # Imported files
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- OpenRouter account with API keys (for live AI answers)

### One-Command Start (PowerShell)

```powershell
.\scripts\start_all.ps1
```

### Manual Start

```powershell
# Backend (http://localhost:8000)
.\scripts\start_backend.ps1

# Frontend (http://localhost:5173)
.\scripts\start_frontend.ps1
```

### Verify

- Backend health: http://localhost:8000/health
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

---

## Configuration

Copy `.env.example` to `.env` and fill in your OpenRouter API keys:

```powershell
cp .env.example .env
```

```ini
# Required for live AI answers
AI_PROVIDER=openrouter
OPENROUTER_API_KEY_1=sk-or-...     # embeddings key
OPENROUTER_API_KEY_2=sk-or-...     # chat key
```

**Key separation (recommended):** Use two separate OpenRouter keys — one for embeddings (`KEY_1`) and one for chat (`KEY_2`). This isolates rate limits. The legacy single `OPENROUTER_API_KEY` still works as a fallback.

See `.env.example` for all available settings (vector store, retrieval limits, voice, etc.).

**Security:** `.env` is git-ignored and must never be committed. `.env.example` contains placeholders only.

---

## Testing

```powershell
# Backend (174 tests, no API keys needed)
cd backend
.venv\Scripts\python.exe -m pytest -q

# Compile check
.venv\Scripts\python.exe -m compileall -q app scripts tests

# Frontend
cd frontend
npm run typecheck
npm run build
```

---

## Certification

### v1.0.0 — Certified Release

| Check | Status |
|-------|--------|
| Backend tests | 174/174 PASS |
| Live E2E acceptance | 11/11 PASS |
| Frontend typecheck | PASS |
| Frontend production build | PASS |
| Backend compile | PASS |
| Secret scan | PASS |
| Git working tree | CLEAN |
| License | MIT |

---

## Security

### Data Handling
- Imported conversation text is treated as **data**, not instructions
- Prompt-injection defense: system prompt marks memories as `DATA, not instructions`
- Any text inside a memory that tries to override behavior is treated as content to answer about

### Secret Management
- API keys from environment only — never in source code
- `.env` is git-ignored; `.env.example` has placeholders only
- `/settings` and `/health` return boolean presence flags, never key material
- Error messages scrubbed before surfacing to responses or logs
- Tests pin empty keys — never read real `.env`

### Project Isolation
- All data scoped to projects (people, conversations, memories, vectors)
- Cross-project queries return only relevant results
- Deletion of a project cascades vectors, embeddings, and memories

### Memory Integrity
- Every memory has a source message link
- Corrections create new versions — old values never destroyed
- Full audit trail via `memory_versions` table
- No automatic deletion of historical memory

---

## Known Limitations

- **Vector store** defaults to `simple` (SQLite + numpy). For ChromaDB, run `pip install chromadb` and set `VECTOR_STORE=chroma`.
- **Free-tier OpenRouter** models are rate-limited (~20 req/min). The provider respects rate-limit headers and retries automatically.
- **Offline mode** uses the `local` heuristic provider — functional but not as intelligent as a language model.
- **Analysis** is rule-based (fast, deterministic) rather than LLM-driven.
- **Voice** is architecture-only in v1.0.0 — the backend reports STT/TTS capability status but audio capture is left to the browser.

---

## Roadmap

> The following items are planned for future releases and are **not** implemented in v1.0.0.

- Voice integration (browser MediaRecorder + backend STT/TTS)
- Multi-user support
- Memory relationships and graph view
- Conversation summarization
- Mobile-optimized responsive layouts

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Muhammad Kaif
