# Personal Memory Chatbot

A personal AI assistant that remembers. Import conversation history, let the app build a persistent memory of who someone is, and then chat with it — every answer is grounded in retrieved memories with cited sources.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)

---

## Table of Contents

- [What It Does](#what-it-does)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running](#running)
- [Testing](#testing)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## What It Does

The Personal Memory Chatbot learns about a person from their conversation history. Import WhatsApp-style chat logs, and the system automatically extracts facts, preferences, habits, and opinions — each linked to the exact message it came from. When you chat, answers are retrieved from these memories and the system tells you how confident it is.

The whole system is designed to be **personally deployable**: SQLite + a local vector store, a single Uvicorn process, and a React frontend. OpenRouter is the only external dependency when you want real AI-powered answers.

---

## Features

**Memory & Learning**
- Automatic extraction of facts, preferences, interests, habits, and opinions
- Confidence scoring with HIGH / MEDIUM / LOW levels
- Memory versioning — full revision history for every create, edit, correction, and delete
- Correction chain — old values are superseded (never overwritten) and linked
- Current-conversation learning — explicit statements are remembered during chat

**Two-Person Projects**
- Project-scoped data isolation (people, conversations, memories, vectors)
- ME / OTHER participant roles
- Default project protection (cannot be deleted)

**Grounded Chat**
- Vector similarity retrieval (person-scoped)
- Lexical fallback when no vector matches
- Source citation — every answer shows which memories it used
- Debug panel with retrieval details

**Import**
- JSON, CSV, TXT, and ZIP formats
- Preview step (read-only) before anything is stored
- Automatic cleaning (duplicates, empty messages, system messages, spam)
- Consent confirmation required

**Analysis**
- Per-person structured profiles (interests, preferences, facts, topics)
- Writing style analysis (tone, vocabulary, greetings, language mix)
- Person merge for duplicate records

**UI**
- Dark premium interface with responsive design
- Real-time backend connection status (CONNECTED / DEGRADED / OFFLINE)
- Project switcher with quick creation
- Animated transitions with reduced-motion support

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

**Key technology choices:**
- **SQLite** — zero-config, single-file database, portable
- **numpy cosine similarity** — zero-dependency vector search
- **OpenRouter** — unified API for chat and embedding models with fallback chains
- **Split-key auth** — separate API keys for embeddings and chat (rate-limit isolation)

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- OpenRouter account with API keys (for live AI answers)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your OpenRouter API keys:

```bash
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

## Running

### Quick Start (PowerShell)

```powershell
# Full stack (backend + frontend)
.\scripts\start_all.ps1

# Or start individually:
.\scripts\start_backend.ps1     # http://localhost:8000
.\scripts\start_frontend.ps1    # http://localhost:5173
```

### Manual Start

```bash
# Backend
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm run dev
```

### Verify

- Backend health: http://localhost:8000/health
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

---

## Testing

```bash
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

## API Reference

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Provider status, embedding compatibility, counts |
| `GET` | `/settings` | Configuration status (no secrets) |
| `POST` | `/chat` | Grounded Q&A with memory retrieval |
| `GET` | `/memories` | List/filter memories |
| `POST` | `/memories` | Add manual memory |
| `PATCH` | `/memories/{id}` | Edit memory |
| `POST` | `/memories/{id}/correct` | Correct memory (retires old value) |
| `DELETE` | `/memories/{id}` | Delete memory |
| `GET` | `/memories/{id}/versions` | Revision history |
| `GET` | `/people` | List people with counts |
| `POST` | `/people/{id}/analyze` | Run profile + style analysis |
| `POST` | `/people/merge` | Merge duplicate people |
| `GET` | `/projects` | List projects |
| `POST` | `/projects` | Create project (two-person) |
| `DELETE` | `/projects/{id}` | Delete project |
| `POST` | `/import/preview` | Read-only import preview |
| `POST` | `/import/json` | Import JSON |
| `POST` | `/import/csv` | Import CSV |
| `POST` | `/import/txt` | Import plain text |
| `POST` | `/import/zip` | Import ZIP archive |
| `GET` | `/export/people` | Export people (JSON) |
| `GET` | `/export/memories` | Export memories (JSON) |
| `GET` | `/voice/status` | Voice capability status |

Full interactive docs: http://localhost:8000/docs (Swagger UI)

---

## Project Structure

```
chatbot/
├── .env                    # Runtime configuration (git-ignored)
├── .env.example            # Configuration template
├── docker-compose.yml      # Docker deployment
├── README.md
├── CHANGELOG.md
├── docs/
│   └── ARCHITECTURE.md     # Technical architecture
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
└── data/                   # Runtime data (git-ignored)
    ├── chatbot.db          # SQLite database
    └── imports/            # Imported files
```

---

## Known Limitations

- **Vector store** defaults to `simple` (SQLite + numpy). For ChromaDB, run `pip install chromadb` and set `VECTOR_STORE=chroma`.
- **Free-tier OpenRouter** models are rate-limited (~20 req/min). The provider respects rate-limit headers and retries automatically.
- **Offline mode** uses the `local` heuristic provider — functional but not as intelligent as a language model.
- **Analysis** is rule-based (fast, deterministic) rather than LLM-driven.
- **Voice** is architecture-only in v1.0.0 — the backend reports STT/TTS capability status but audio capture is left to the browser.

---

## Roadmap

- Voice integration (browser MediaRecorder + backend STT/TTS)
- Multi-user support
- Memory relationships and graph view
- Conversation summarization
- Mobile-optimized responsive layouts

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Muhammad Kaif
