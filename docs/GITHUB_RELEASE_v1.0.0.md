# GitHub Release Notes — v1.0.0

---

## v1.0.0 — Personal Memory Chatbot

**Initial production release.**

---

### Overview

A privacy-conscious personal memory chatbot that imports conversations, analyzes long-term communication history, builds evidence-backed memories, and provides grounded answers using hybrid retrieval and source-aware context.

---

### Features

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

### Architecture

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy 2.0, Pydantic
- **Frontend:** React 18, TypeScript, Vite 5
- **Data:** SQLite (authoritative), NumPy cosine similarity (vector search)
- **AI:** OpenRouter with split-key auth and model fallback chains
- **Testing:** pytest (174 tests), TypeScript typecheck, Vite build, live E2E (11 tests)

---

### Security

- API keys from environment only — never in source code
- `.env` git-ignored; `.env.example` has placeholders only
- `/settings` and `/health` never return key material
- Prompt-injection defense: memories marked as DATA, not instructions
- Import requires explicit consent confirmation
- Error messages scrubbed before surfacing

---

### Testing

| Check | Result |
|-------|--------|
| Backend tests | 174/174 PASS |
| Live E2E acceptance | 11/11 PASS |
| Frontend typecheck | PASS |
| Frontend production build | PASS |
| Backend compile | PASS |
| Secret scan | PASS |

---

### Known Limitations

- Vector store defaults to `simple` (SQLite + numpy). ChromaDB optional via `pip install chromadb`
- Free-tier OpenRouter models rate-limited (~20 req/min), provider auto-retries
- Offline `local` provider uses keyword heuristics, not a language model
- Analysis pipeline is rule-based (deterministic) rather than LLM-driven
- Voice layer is architecture-only in v1.0.0

---

### Installation

```bash
git clone https://github.com/your-username/personal-memory-chatbot.git
cd personal-memory-chatbot
cp .env.example .env
# Edit .env with your OpenRouter API keys

# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install

# Run
cd ..
.\scripts\start_all.ps1
```

---

### License

MIT License — Copyright (c) 2026 Muhammad Kaif
