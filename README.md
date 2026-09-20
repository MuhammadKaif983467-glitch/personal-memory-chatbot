# Personal Memory Chatbot

A privacy-conscious personal memory chatbot that imports conversations, analyzes long-term communication history, builds evidence-backed memories, and provides grounded answers using hybrid retrieval and source-aware context.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue.svg)](https://www.typescriptlang.org/)
[![OpenRouter](https://img.shields.io/badge/AI-OpenRouter-purple.svg)](https://openrouter.ai/)
[![Tests](https://img.shields.io/badge/Backend%20Tests-174%20passed-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)
[![Version](https://img.shields.io/badge/Version-1.0.0-brightgreen.svg)](#project-status)

---

## Table of Contents

* [Overview](#overview)
* [Core Features](#core-features)
* [How It Works](#how-it-works)
* [Screenshots](#screenshots)
* [Architecture](#architecture)
* [Technology Stack](#technology-stack)
* [Project Structure](#project-structure)
* [Quick Start](#quick-start)
* [Configuration](#configuration)
* [Conversation Import](#conversation-import)
* [Memory System](#memory-system)
* [Two-Person Projects](#two-person-projects)
* [Hybrid Retrieval](#hybrid-retrieval)
* [Current-Conversation Learning](#current-conversation-learning)
* [Voice Architecture](#voice-architecture)
* [API](#api)
* [Testing](#testing)
* [Project Status](#project-status)
* [Security](#security)
* [Known Limitations](#known-limitations)
* [Roadmap](#roadmap)
* [License](#license)

---

## Overview

Personal Memory Chatbot is an AI application designed to build long-term conversational memory from imported and current conversations.

Instead of treating every conversation as isolated, the system stores structured memories and links them to their original source messages.

The chatbot uses those memories during future conversations to provide context-aware responses.

The system supports:

* Conversation history import
* Two-person projects
* Structured long-term memories
* Memory corrections and version history
* Source-linked evidence
* Hybrid vector and lexical retrieval
* Confidence scoring
* Current-conversation learning
* Project-level data isolation
* OpenRouter AI providers
* Offline provider support
* Prompt-injection protection
* Voice capability architecture

The application is designed for personal deployment using SQLite, a local vector store, FastAPI, React, and an OpenRouter-compatible AI provider.

---

## Core Features

### Two-Person Project Model

Each project represents a two-person conversation environment.

* One participant is assigned the `ME` role.
* One participant is assigned the `OTHER` role.
* People, conversations, memories, and vectors are scoped to the project.
* Projects provide data isolation.
* The default project is protected from accidental deletion.

This model allows users to import their own conversation history and explicitly identify which participant represents themselves.

---

### Conversation Import

Supported formats include:

* JSON
* CSV
* TXT
* ZIP

The import workflow includes:

* Read-only preview before storage
* Message normalization
* Duplicate detection
* Empty-message filtering
* System-message filtering
* Spam filtering
* Consent confirmation
* Idempotent re-import protection

Imported data is processed before becoming part of the persistent memory system.

---

### Persistent Memory

The memory system extracts structured information from conversations.

Supported memory categories include:

* Facts
* Preferences
* Interests
* Habits
* Opinions

Each memory is connected to its source message.

Memory records include information such as:

* Memory content
* Person
* Project
* Memory type
* Confidence
* Importance
* Source message
* Creation time
* Revision history
* Status

This creates an evidence-backed memory layer instead of relying on untraceable chatbot context.

---

### Memory Corrections and Versioning

The system does not silently overwrite historical memories.

When a memory needs correction:

1. The existing memory is retained.
2. Its status is updated.
3. A replacement memory is created.
4. The relationship between the old and new versions is recorded.
5. The revision history remains available.

The `memory_versions` system provides an audit trail for memory changes.

This approach preserves historical context while allowing the current state to remain accurate.

---

### Current-Conversation Learning

The chatbot also learns from new conversations.

Examples include statements such as:

```text
I now prefer X over Y.
```

The system identifies learning events such as:

* `NEW`
* `UPDATED`
* `CORRECTION`
* `NO_MEMORY`

When a new statement conflicts with an existing memory, the system creates a correction or replacement relationship instead of destroying the historical record.

---

### Hybrid Retrieval

The chatbot uses multiple retrieval strategies.

#### Vector Retrieval

Semantic similarity is used to locate memories related to the current question.

The default vector implementation uses:

* SQLite
* NumPy
* Cosine similarity

#### Lexical Fallback

When vector retrieval produces no suitable results, the system falls back to lexical matching.

This provides a second retrieval path for exact or keyword-oriented queries.

#### Ranking

Retrieved memories are ranked using factors including:

* Similarity
* Recency
* Importance
* Confidence

The resulting memories are passed into the response generation process.

---

### Source and Evidence Grounding

Responses are connected to the memories used to generate them.

The application provides:

* Memory source information
* Confidence information
* Retrieval details
* Ranked memory results
* Similarity information
* Source evidence

This helps users understand where remembered information came from.

---

### Project Isolation

Project-level isolation prevents unrelated conversation data from being mixed.

The project boundary applies to:

* People
* Conversations
* Messages
* Memories
* Memory versions
* Vectors
* Embeddings

Queries are restricted to the active project.

Project deletion also removes associated project data according to the application's database relationships.

---

### Premium Chat Interface

The frontend provides a modern dark interface with:

* Chat interface
* Conversation history
* Project switcher
* Project creation
* Connection status
* Memory feedback
* Import workflow
* Memory views
* Settings
* Voice capability status
* Responsive layouts
* Reduced-motion support

Connection states include:

```text
CONNECTED
DEGRADED
OFFLINE
```

---

### Voice Architecture

The backend exposes voice capability information through:

```text
GET /voice/status
```

The architecture supports pluggable speech providers.

Version 1.0 keeps audio capture and playback primarily on the browser side through browser audio capabilities.

Full voice provider integration is part of the roadmap.

---

### Security

Security features include:

* Environment-based API key configuration
* `.env` exclusion from Git
* Placeholder-only `.env.example`
* Secret-safe health and settings endpoints
* Prompt-injection protection
* Import consent confirmation
* Error-message sanitization
* Project isolation
* Memory audit history

Imported conversation text is treated as data rather than executable instructions.

---

### OpenRouter Integration

The application supports OpenRouter through an OpenAI-compatible API interface.

The provider architecture supports:

* Separate embedding and chat keys
* Chat model fallback chains
* Embedding model fallback chains
* Rate-limit handling
* Retry logic
* Offline local provider

Two-key configuration is supported:

```text
OPENROUTER_API_KEY_1
```

for embeddings, and:

```text
OPENROUTER_API_KEY_2
```

for chat.

A legacy:

```text
OPENROUTER_API_KEY
```

configuration remains supported as a fallback.

---

## How It Works

The overall processing flow is:

```text
                    User
                      │
                      ▼
             React Frontend
                      │
                      ▼
              FastAPI Backend
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
    Conversation Data        Chat Request
          │                       │
          ▼                       ▼
   Import / Analysis        Retrieval Service
          │                       │
          ▼                ┌──────┴──────┐
       Memories            │             │
          │                ▼             ▼
          │             Vector       Lexical
          │            Retrieval    Retrieval
          │                │             │
          └────────────────┴─────────────┘
                           │
                           ▼
                    Ranked Memories
                           │
                           ▼
                   Confidence Service
                           │
                           ▼
                    AI Provider
                           │
                           ▼
                 Grounded Response
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
              Answer             Sources
```

### Chat Request Flow

```text
Frontend
   ↓
POST /chat
   ↓
chat_service
   ↓
retrieval_service
   ↓
embedding generation
   ↓
vector search
   ↓
lexical fallback if required
   ↓
memory ranking
   ↓
confidence calculation
   ↓
AI provider
   ↓
structured response
   ↓
sources + confidence + learning status
```

---

## Screenshots

Screenshots will be added from a live application instance.

Planned screenshots:

| Screen                           | Purpose                             |
| -------------------------------- | ----------------------------------- |
| `docs/screenshots/dashboard.png` | Main application dashboard          |
| `docs/screenshots/chat.png`      | Grounded chat response with sources |
| `docs/screenshots/memories.png`  | Memory timeline and revisions       |
| `docs/screenshots/people.png`    | Person profiles and analysis        |
| `docs/screenshots/import.png`    | Conversation import and preview     |
| `docs/screenshots/settings.png`  | Configuration and provider status   |

The screenshots section will be updated before the public portfolio release.

---

## Architecture

The project follows a modular frontend and backend architecture.

```text
┌─────────────────────────────────────────┐
│              React Frontend             │
│        TypeScript + Vite + UI           │
└────────────────────┬────────────────────┘
                     │ HTTP
                     ▼
┌─────────────────────────────────────────┐
│             FastAPI Backend             │
│                REST API                 │
└────────────────────┬────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
   AI Services   Core Services  API Layer
        │            │
        │            ▼
        │       Database Layer
        │            │
        │            ▼
        │          SQLite
        │
        ▼
   OpenRouter
        │
        ├── Chat Models
        └── Embedding Models

              Vector Layer
                   │
             ┌─────┴─────┐
             ▼           ▼
          NumPy       ChromaDB
          Default     Optional
```

Detailed technical architecture:

```text
docs/ARCHITECTURE.md
```

---

## Technology Stack

### Frontend

| Technology | Purpose                           |
| ---------- | --------------------------------- |
| React 18   | User interface                    |
| TypeScript | Type safety                       |
| Vite 5     | Build tool and development server |

### Backend

| Technology     | Purpose             |
| -------------- | ------------------- |
| Python 3.10+   | Application runtime |
| FastAPI        | REST API            |
| Uvicorn        | ASGI server         |
| SQLAlchemy 2.0 | Database ORM        |
| Pydantic       | Data validation     |

### Data Layer

| Technology          | Purpose                             |
| ------------------- | ----------------------------------- |
| SQLite              | Primary relational database         |
| NumPy               | Vector calculations                 |
| Simple Vector Store | Default local vector implementation |
| ChromaDB            | Optional vector backend             |

### AI Layer

| Technology               | Purpose                     |
| ------------------------ | --------------------------- |
| OpenRouter               | AI provider gateway         |
| OpenAI-compatible API    | Provider interface          |
| Chat fallback chain      | Model availability fallback |
| Embedding fallback chain | Embedding model fallback    |
| Local provider           | Offline operation           |

### Testing

| Tool                | Purpose                         |
| ------------------- | ------------------------------- |
| pytest              | Backend testing                 |
| TypeScript compiler | Frontend type checking          |
| Vite                | Production build verification   |
| compileall          | Python compilation checks       |
| Secret scan         | Credential exposure checks      |
| Live E2E checks     | Runtime acceptance verification |

---

## Project Structure

```text
chatbot/
│
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── CHANGELOG.md
├── docker-compose.yml
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── GITHUB_DESCRIPTION.md
│   ├── PORTFOLIO.md
│   ├── LINKEDIN_PROJECT.md
│   ├── DEMO_SCRIPT.md
│   ├── SCREENSHOT_PLAN.md
│   ├── RESUME_ENTRY.md
│   └── GITHUB_RELEASE_v1.0.0.md
│
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   ├── api/
│   │   ├── core/
│   │   ├── database/
│   │   ├── services/
│   │   ├── vectorstore/
│   │   └── factory.py
│   │
│   ├── scripts/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── types.ts
│   └── package.json
│
├── scripts/
│   ├── start_all.ps1
│   ├── start_backend.ps1
│   └── start_frontend.ps1
│
├── tests/
│   └── .gitkeep
│
└── data/
    ├── chatbot.db
    └── imports/
```

Runtime data and secrets should remain outside version control.

---

## Quick Start

### Prerequisites

Install:

* Python 3.10 or newer
* Node.js 18 or newer
* npm
* Git

For live AI responses, configure an OpenRouter account and API keys.

---

### Clone the Repository

```powershell
git clone <YOUR_REPOSITORY_URL>
cd chatbot
```

---

### Configure Environment

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

Open:

```text
.env
```

Configure the required provider settings.

---

### Start the Full Application

From the project root:

```powershell
.\scripts\start_all.ps1
```

---

### Start the Backend Manually

```powershell
.\scripts\start_backend.ps1
```

Backend:

```text
http://localhost:8000
```

---

### Start the Frontend Manually

Open another PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

### API Documentation

Once the backend is running:

```text
http://localhost:8000/docs
```

Health endpoint:

```text
http://localhost:8000/health
```

Frontend:

```text
http://localhost:5173
```

---

## Configuration

The application uses environment variables.

Copy:

```text
.env.example
```

to:

```text
.env
```

Example configuration:

```ini
AI_PROVIDER=openrouter

OPENROUTER_API_KEY_1=your_embedding_key
OPENROUTER_API_KEY_2=your_chat_key

VECTOR_STORE=simple
```

Do not place real API keys in source code.

Do not commit `.env`.

---

### Split-Key Configuration

The recommended provider configuration separates embedding and chat traffic.

```text
KEY_1
  ↓
Embedding requests

KEY_2
  ↓
Chat requests
```

This separates provider usage between the two workloads.

The application also supports the legacy single-key configuration:

```ini
OPENROUTER_API_KEY=your_key
```

---

## Conversation Import

The import system is designed for personal conversation exports.

Supported formats:

```text
JSON
CSV
TXT
ZIP
```

The workflow is:

```text
Select File
    ↓
Preview
    ↓
Validate
    ↓
Identify Participants
    ↓
Choose ME
    ↓
Confirm Consent
    ↓
Import
    ↓
Process Messages
    ↓
Extract Memories
    ↓
Store Sources
    ↓
Build Retrieval Index
```

The preview stage is read-only.

This gives users an opportunity to review the imported data before persistent storage.

---

## Memory System

The memory system connects extracted knowledge to source evidence.

Example conceptual record:

```text
Person:
Other

Memory:
Prefers coffee over tea

Type:
Preference

Confidence:
HIGH

Source:
Original conversation message

Status:
ACTIVE
```

The system keeps historical versions when corrections occur.

```text
Original Memory
      │
      ▼
Correction
      │
      ▼
Replacement Memory
```

Historical information remains available through the revision trail.

---

## Two-Person Projects

Each project has two roles:

```text
ME
OTHER
```

Example:

```text
Project: Personal Conversation

ME:
Kaif

OTHER:
Zain
```

The project stores its own:

* People
* Conversations
* Messages
* Memories
* Memory versions
* Vectors

The same application supports separate projects without mixing their memory data.

---

## Hybrid Retrieval

The retrieval system uses semantic and lexical approaches.

### Vector Search

The application converts searchable content into embeddings.

It then calculates semantic similarity against the query.

The default implementation uses NumPy-based vector calculations.

### Lexical Search

If vector retrieval does not provide suitable matches, lexical matching provides a fallback.

This supports exact terms and keyword-focused questions.

### Retrieval Ranking

The ranking process considers:

```text
Similarity
×
Recency
×
Importance
×
Confidence
```

The resulting memories are used as context for response generation.

---

## Current-Conversation Learning

The chatbot processes new information during ongoing conversations.

Learning outcomes include:

```text
NEW
UPDATED
CORRECTION
NO_MEMORY
```

Example:

```text
User:
I stopped drinking tea. I prefer coffee now.

System:
CORRECTION

Previous:
Prefers tea

Current:
Prefers coffee
```

The previous memory remains part of the historical record.

---

## Voice Architecture

Voice support is structured around a provider abstraction.

Current version:

```text
Voice Capability API
        ↓
Provider Status
        ↓
Browser Audio Layer
```

The backend exposes:

```text
GET /voice/status
```

Version 1.0 focuses on the architecture and capability layer.

Full speech-to-text and text-to-speech integration is planned for a future release.

---

## API

The backend provides REST endpoints for application functionality.

Core areas include:

```text
/health
/settings
/chat
/search
/conversations
/memories
/people
/projects
/import
/voice/status
```

Interactive API documentation is available through FastAPI:

```text
http://localhost:8000/docs
```

The exact endpoint schemas are available in the running API documentation.

---

## Testing

The project includes automated backend and frontend verification.

### Backend Tests

From:

```text
backend/
```

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Current recorded result:

```text
174 passed
```

### Python Compilation

```powershell
.venv\Scripts\python.exe -m compileall -q app scripts tests
```

### Frontend Typecheck

From:

```text
frontend/
```

Run:

```powershell
npm run typecheck
```

### Production Build

```powershell
npm run build
```

### Verification Areas

The project verification process covers:

* Backend unit tests
* API behavior
* Memory operations
* Project isolation
* Import behavior
* Security checks
* Secret handling
* Frontend type checking
* Production frontend build
* Python compilation
* Runtime acceptance checks

Provider-dependent tests depend on external model availability and provider rate limits.

---

## Project Status

### Version 1.0.0

The current release contains the core personal memory architecture.

Implemented areas include:

* Two-person projects
* Conversation import
* Persistent memories
* Memory corrections
* Memory version history
* Source-linked memories
* Hybrid retrieval
* Confidence scoring
* Current-conversation learning
* Project isolation
* OpenRouter integration
* Split-key provider configuration
* Offline provider architecture
* Security controls
* Premium chat interface
* Voice capability architecture

### Verification

Recorded automated verification:

| Check                     | Result     |
| ------------------------- | ---------- |
| Backend tests             | 174 passed |
| Frontend typecheck        | Passed     |
| Frontend production build | Passed     |
| Python compile check      | Passed     |
| Secret scan               | Passed     |
| API authentication        | Verified   |
| Chat authentication       | Verified   |
| Git working tree          | Clean      |
| License                   | MIT        |

External AI provider behavior depends on model availability, account limits, rate limits, and network conditions.

---

## Security

### Data Handling

Imported conversation text is treated as application data.

Memory content is explicitly separated from system instructions.

Content attempting to change application behavior through imported messages is treated as conversational data.

---

### Secret Management

API keys are loaded through environment configuration.

The repository uses:

```text
.env
.env.example
.gitignore
```

The `.env` file should never be committed.

The example configuration contains placeholders only.

Health and settings endpoints expose configuration status rather than secret values.

---

### Project Isolation

Application data is scoped by project.

Project-scoped data includes:

* People
* Conversations
* Messages
* Memories
* Vectors
* Embeddings

Cross-project retrieval is restricted to the active project.

---

### Memory Integrity

The memory system preserves historical changes.

Corrections create new memory versions rather than silently destroying old values.

Each memory is linked to source evidence where available.

The revision trail records memory changes.

---

## Known Limitations

### OpenRouter Rate Limits

Free-tier models have provider-specific limits.

Availability depends on the current OpenRouter account and model conditions.

Provider failures do not represent failures in the local application architecture.

---

### Offline Provider

The local provider supports operation without an external AI key.

Its responses are heuristic-based and do not provide the same language-generation capabilities as an external language model.

---

### Analysis

Conversation analysis is primarily rule-based in version 1.0.

This provides deterministic behavior for supported analysis operations.

---

### Voice

The current release provides the voice capability architecture and status API.

Full integrated speech-to-text and text-to-speech workflows remain future work.

---

### Vector Store

The default vector store is:

```text
simple
```

It uses SQLite and NumPy.

ChromaDB remains an optional alternative.

---

## Roadmap

Future releases are planned around the following areas:

### Voice

* Browser MediaRecorder integration
* Speech-to-text provider integration
* Text-to-speech provider integration
* Voice conversation mode

### Memory

* Memory relationship graph
* Memory graph visualization
* Improved semantic clustering
* Conversation summarization
* Advanced memory conflict resolution

### Application

* Multi-user support
* Mobile-focused layouts
* Improved import adapters
* Additional conversation export formats
* Advanced analytics

### AI

* Additional model providers
* Local model support
* Improved retrieval strategies
* Better context selection
* More advanced memory extraction

---

## Documentation

Additional project documentation is available in:

```text
docs/
```

Important documents include:

```text
docs/ARCHITECTURE.md
docs/PORTFOLIO.md
docs/LINKEDIN_PROJECT.md
docs/DEMO_SCRIPT.md
docs/SCREENSHOT_PLAN.md
docs/RESUME_ENTRY.md
docs/GITHUB_RELEASE_v1.0.0.md
```

---

## License

This project is licensed under the MIT License.

See:

```text
LICENSE
```

Copyright (c) 2026 Muhammad Kaif

