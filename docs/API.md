# API Reference

REST API documentation for the Personal Memory Chatbot backend.

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs`

## Health

### GET /health

Returns provider status, embedding compatibility, and data counts.

**Response:**
```json
{
  "status": "ok",
  "provider": "openrouter",
  "embedding_compatible": true,
  "memory_count": 5021,
  "message_count": 1404
}
```

## Settings

### GET /settings

Returns safe configuration status. Never exposes API keys.

**Response:**
```json
{
  "app_version": "3.2.0",
  "ai_provider": "openrouter",
  "vector_store": "simple",
  "consent_required": true
}
```

## Chat

### POST /chat

Send a message and receive a grounded AI response.

**Request:**
```json
{
  "message": "What does Ali prefer?",
  "person_id": 7,
  "conversation_id": 2,
  "sender_name": "Kaif"
}
```

**Response:**
```json
{
  "reply": "Based on what I remember...",
  "confidence": "HIGH",
  "sources": [...],
  "learned": "NO_MEMORY"
}
```

### GET /conversations

List conversations, optionally filtered by `project_id`.

**Query:** `project_id` (optional)

### GET /conversations/{conversation_id}

Get a single conversation by ID.

### DELETE /conversations/{conversation_id}

Delete a conversation and all its messages.

### GET /conversations/{conversation_id}/participants

List participants for a conversation.

### GET /messages

List messages with pagination.

**Query:** `limit`, `offset`, `person_id`, `conversation_id`

**Response:**
```json
{
  "items": [...],
  "total": 1404,
  "limit": 200,
  "offset": 0
}
```

### GET /messages/{message_id}

Get a single message by ID.

### DELETE /messages/{message_id}

Delete a single message.

## Import

### POST /import/universal

Universal import with automatic platform detection.

**Request:** Multipart form data with file and parameters.

### POST /import/universal/inspect

Inspect a file to detect platform/format without importing.

### POST /import/universal/preview

Preview an upload with automatic platform detection.

### POST /import/json

Import from JSON payload.

**Request:**
```json
{
  "consent_confirmed": true,
  "conversation": {
    "title": "Chat with Ali",
    "person": "Ali",
    "source": "whatsapp"
  },
  "messages": [
    {
      "sender": "Ali",
      "content": "Hello",
      "timestamp": "2026-01-01T12:00:00"
    }
  ]
}
```

### POST /import/csv

Import from CSV file upload.

### POST /import/txt

Import from plain text file upload.

### POST /import/zip

Import from ZIP archive (uses largest text file).

### POST /import/jsonl

Import from JSONL (one JSON object per line).

### POST /import/dataset

Import a full multi-participant dataset.

## Export

All export endpoints accept an optional `project_id` query parameter.

### GET /export/conversations

Export conversations as JSON.

### GET /export/messages

Export messages as JSON.

### GET /export/memories

Export memories as JSON.

### GET /export/people

Export people as JSON.

## Projects

### POST /projects

Create a new project.

### GET /projects

List all projects with stats.

### GET /projects/{project_id}

Get detailed project info.

### PATCH /projects/{project_id}

Update a project's name.

### DELETE /projects/{project_id}

Delete a project and all associated data.

### GET /projects/{project_id}/people

List people within a project.

### GET /projects/{project_id}/conversations

List conversations within a project.

### GET /projects/{project_id}/memories

List memories within a project with filters.

## People

### GET /people

List all people with message counts.

### GET /people/{person_id}

Get a single person by ID.

### GET /people/{person_id}/profile

Get the generated profile for a person.

### GET /people/{person_id}/style

Get writing-style analysis for a person.

### POST /people/{person_id}/analyze

Trigger full analysis pipeline for a person.

### POST /people/merge

Merge two person records.

## Memories

### GET /memories

List memories with filters (person, type, confidence, status).

### GET /memories/{memory_id}

Get a single memory by ID.

### GET /memories/{memory_id}/versions

Get version history for a memory.

### POST /memories

Manually create a new memory.

### POST /memories/{memory_id}/correct

Correct a wrong memory (creates replacement).

### PATCH /memories/{memory_id}

Edit a memory in place.

### DELETE /memories/{memory_id}

Permanently delete a memory.

### POST /memories/{memory_id}/archive

Archive a memory.

### POST /memories/{memory_id}/restore

Restore an archived memory.

### POST /memories/confirm

Confirm, edit, or discard a proposed memory.

### POST /memories/search

Search memories by text query.

## Search

### POST /search

Unified search across messages, memories, and conversations.

**Request:**
```json
{
  "query": "hello",
  "project_id": 1
}
```

### GET /conversations/{conversation_id}/analysis

Deterministic conversation analysis (topics, cues).

## Voice

### GET /voice/status

Report STT/TTS capability status.
