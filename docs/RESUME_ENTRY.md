# Resume / CV Entry

---

## Project

**Personal Memory Chatbot**

---

## Technology

Python, FastAPI, React, TypeScript, SQLite, SQLAlchemy, Vector Retrieval, OpenRouter

---

## Description

Full-stack AI chatbot that imports conversation history, extracts evidence-backed memories with confidence scoring and versioning, and provides grounded answers using hybrid retrieval with source citations.

---

## Engineering Bullets

1. **Designed and implemented a persistent memory system** with append-only versioning, correction chains, and confidence scoring — wrong memories are superseded (never overwritten) with full audit trails linking every version to its creator and timestamp

2. **Built a hybrid retrieval pipeline** combining cosine similarity vector search with lexical fallback, ranking results by similarity, recency, importance, and confidence to ensure grounded answers even when no vector match exists

3. **Implemented current-conversation learning** that detects explicit user statements in real-time, extracts new memories, and automatically supersedes conflicting active memories with correction links

4. **Developed a split-key authentication architecture** isolating embedding and chat API keys for rate-limit separation, with automatic provider fallback chains for both chat and embedding models

5. **Achieved 174/174 backend test coverage** across import, retrieval, memory lifecycle, project isolation, conversation learning, and provider switching, plus 11 live end-to-end acceptance tests verifying the full system

6. **Built a React/TypeScript frontend** with premium dark UI, real-time backend connection status monitoring, project-scoped data views, and responsive design with accessibility support

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Backend tests | 174/174 PASS |
| Live E2E tests | 11/11 PASS |
| Frontend typecheck | PASS |
| Frontend build | PASS |
| Version | v1.0.0 |
| License | MIT |
