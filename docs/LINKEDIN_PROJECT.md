# LinkedIn Project Description

---

## Short Description

Built a full-stack Personal Memory Chatbot that imports conversation history, extracts evidence-backed memories with confidence scoring, and provides grounded answers using hybrid retrieval with source citations. Python/FastAPI backend, React/TypeScript frontend, SQLite + NumPy vector store.

---

## Longer Description

I built the Personal Memory Chatbot - a full-stack application that learns about people from their conversation history.

The system imports real chat logs (JSON, CSV, TXT, ZIP), automatically extracts facts, preferences, habits, and opinions using rule-based analysis, and stores them as persistent memories with confidence scoring and full versioning.

When you chat, the system embeds your question, retrieves the most relevant memories using cosine similarity (with lexical fallback), builds grounded context, and generates an answer with source citations. Every answer reports its confidence level (HIGH/MEDIUM/LOW) and shows exactly which memories it used.

Key engineering challenges I solved:
- Memory versioning with append-only audit trails
- Current-conversation learning that detects corrections
- Hybrid retrieval combining vector similarity with lexical search
- Split-key authentication for rate-limit isolation
- 174 backend tests plus 11 live E2E acceptance tests

Tech: Python, FastAPI, React, TypeScript, SQLite, SQLAlchemy, NumPy, OpenRouter

---

## Technical Skills

- Python
- FastAPI
- React
- TypeScript
- SQLite
- SQLAlchemy
- Vector Search / RAG
- OpenRouter / LLM Integration
- REST API Design
- Software Testing

---

## Suggested Project Headline

Personal Memory Chatbot - Full-Stack AI That Remembers and Cites Sources

---

## Suggested LinkedIn Post

Excited to share my latest project: the Personal Memory Chatbot (v1.0.0).

What it does:
- Imports real conversation history (WhatsApp, chat logs)
- Automatically extracts facts, preferences, and habits as persistent memories
- Answers questions grounded in retrieved memories with source citations
- Handles corrections: when you change your mind, it supersedes the old memory and creates a new one with a full audit trail

Technical highlights:
- Python/FastAPI backend with SQLAlchemy + SQLite
- React/TypeScript frontend with Vite
- Hybrid retrieval: cosine similarity vector search with lexical fallback
- Split-key authentication for rate-limit isolation
- Memory versioning with append-only audit trails
- 174 backend tests + 11 live E2E acceptance tests

The whole system runs locally with OpenRouter as the only external dependency. No data leaves your machine except to the AI provider you configure.

Built with: Python, FastAPI, React, TypeScript, SQLite, NumPy, OpenRouter

#python #fastapi #react #typescript #ai #llm #chatbot #rag #machinelearning
