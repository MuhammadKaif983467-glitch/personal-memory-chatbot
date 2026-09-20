# Portfolio Project Description

---

### Project Title

**Personal Memory Chatbot**

---

### One-Line Description

A full-stack AI chatbot that imports conversations, builds persistent evidence-backed memories, and provides grounded answers with source citations using hybrid retrieval.

---

### Problem

Most chatbots treat every conversation as ephemeral. They don't remember who you talked to last week, what preferences you expressed, or how your opinions changed over time. Existing "memory" solutions are either cloud-dependent, lack evidence trails, or can't handle corrections and updates to what they've learned.

---

### Solution

The Personal Memory Chatbot solves this by:

1. **Importing** real conversation history (WhatsApp-style chats) from multiple formats
2. **Analyzing** the data to extract structured facts, preferences, habits, and opinions
3. **Building** a persistent memory store with confidence scoring and full versioning
4. **Answering** questions grounded in retrieved memories, with source citations

When a user says "I changed my favorite language from Java to Python," the system automatically detects the correction, supersedes the old memory, creates a new one, and maintains a full audit trail — all within a single chat turn.

---

### Architecture

```
React + TypeScript (Vite)
        │
        ▼
FastAPI + SQLAlchemy (SQLite)
        │
   ┌────┼────────────┐
   ▼    ▼            ▼
Services  AI Provider  Vector Store
   │     (OpenRouter)  (SQLite + numpy)
   ▼
SQLite Database
```

**Key architectural decisions:**
- SQLite for zero-config, portable storage
- NumPy cosine similarity for zero-dependency vector search
- Split-key authentication for rate-limit isolation
- Model fallback chains for provider resilience
- Append-only memory versioning for audit trails

---

### Key Engineering Challenges

| Challenge | Approach |
|-----------|----------|
| **Long-term memory** | Rule-based extraction with confidence scoring and person/project scoping |
| **Memory versioning** | Append-only `memory_versions` table with actor tracking and status lifecycle |
| **Source evidence** | Every memory linked to its source message via `source_message_id` |
| **Hybrid retrieval** | Vector similarity + lexical fallback when no vector matches |
| **Import idempotency** | Deduplication, cleaning, and idempotent re-imports |
| **Project isolation** | Full data scoping per project (people, conversations, memories, vectors) |
| **Provider failures** | Automatic fallback chains for both chat and embedding models |
| **Rate limiting** | Split-key auth, rate-limit header awareness, automatic retry |
| **Current-conversation learning** | Real-time extraction of "me" statements with correction detection |
| **Prompt injection defense** | System prompt marks memories as DATA, not instructions |
| **Testing at scale** | 174 backend tests + 11 live E2E acceptance tests |

---

### Results

| Metric | Value |
|--------|-------|
| Backend tests | 174/174 PASS |
| Live E2E acceptance | 11/11 PASS |
| Version | v1.0.0 |
| Frontend build | Production-ready |
| Secret scan | PASS |
| License | MIT |

---

### Technologies

| Category | Technologies |
|----------|-------------|
| **Frontend** | React 18, TypeScript, Vite 5 |
| **Backend** | Python 3.10+, FastAPI, SQLAlchemy 2.0, Pydantic |
| **Data** | SQLite, NumPy, optional ChromaDB |
| **AI** | OpenRouter, OpenAI-compatible API, embedding fallback chains |
| **Testing** | pytest, TypeScript typecheck, Vite production build, live E2E |

---

### Engineering Highlights

1. **Evidence-backed memories** — Every memory links to its source message, enabling verifiable provenance
2. **Correction chains** — Wrong memories are superseded, not deleted, with full revision history
3. **Hybrid retrieval** — Vector similarity with lexical fallback ensures no question goes unanswered
4. **Split-key authentication** — Separate API keys for embeddings and chat isolate rate limits
5. **Zero-dependency vector search** — NumPy cosine similarity works without ChromaDB
6. **174 hermetic tests** — Backend test suite covers import, retrieval, versioning, learning, and provider switching
