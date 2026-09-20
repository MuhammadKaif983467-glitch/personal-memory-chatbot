# Changelog

All notable changes to the Personal Memory Chatbot.

## v1.0.0

Initial production release.

### Features

- **Persistent memory system** — rule-based extraction of facts, preferences, interests, habits, and opinions from conversation history, each traced to its source message
- **Memory confidence & versioning** — confidence scoring, correction (old value superseded, never overwritten), full revision history with actor tracking
- **Two-person project model** — project-scoped data isolation with ME/OTHER participant roles
- **Current-conversation learning** — automatic memory extraction from explicit "me" statements during chat, with correction detection
- **Grounded chat** — hybrid retrieval (vector similarity + lexical fallback), confidence levels (HIGH/MEDIUM/LOW), source citation
- **Profile & style analysis** — per-person structured profiles and writing style summaries
- **Multi-format import** — JSON, CSV, TXT, ZIP with preview step, cleaning, and consent
- **Model fallback chains** — automatic fallback when a model is unavailable
- **Split-key authentication** — separate keys for embeddings and chat
- **Voice layer (architecture)** — STT/TTS capability status (disabled by default)
- **Dark premium UI** — responsive design with animations, connection status, project switcher

### Backend

- FastAPI + SQLAlchemy (SQLite) + numpy vector store
- OpenRouter provider with model fallback chains
- 174 hermetic tests covering import, retrieval, memory lifecycle, projects, learning, and provider switching

### Frontend

- React 18 + Vite 5 + TypeScript
- Pages: Chat, Memories, People, Import, Settings
- Real-time connection status (CONNECTED / DEGRADED / OFFLINE)

### Verified

- Backend tests: 174/174 pass
- Live E2E acceptance: 11/11 pass
- TypeScript typecheck: pass
- Frontend production build: pass
- Database integrity: verified (477 memories, 263 embeddings)
