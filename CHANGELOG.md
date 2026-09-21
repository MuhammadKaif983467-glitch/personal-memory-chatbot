# Changelog

All notable changes to the Personal Memory Chatbot.

## [3.3.0] - 2026-09-21

Production release — database hardening, FTS5, backup/recovery, memory relationships, summaries, Playwright E2E.

### V3.3 Phase 1 — Database Hardening & FTS Foundation

#### Added

- **SQLite foreign-key enforcement** — `PRAGMA foreign_keys = ON` via SQLAlchemy event listener on every connection
- **FTS5 full-text search** — external-content virtual table `messages_fts` with `unicode61` tokenizer, project-scoped search
- **FTS5 synchronization triggers** — `INSERT`/`UPDATE`/`DELETE` triggers keep FTS index in sync with messages table
- **FTS5 query sanitization** — strips FTS5 operators (`*`, `"`, `AND`, `OR`, `NOT`, `NEAR`) to prevent injection
- **Composite indexes** — 10 verified indexes on hot query paths (`messages(conversation_id, timestamp)`, `memories(project_id, person_id, memory_type, status)`, etc.)
- **Schema migration versioning** — `schema_migrations` table tracks applied migrations, idempotent execution
- **Migration V3.3.001** — cleans orphaned `source_message_id` references in `memories` and `memory_versions`
- **ON DELETE clauses** — proper `SET NULL` / `CASCADE` on all foreign keys for new databases
- **FTS fallback hierarchy** — FTS5 → LIKE-based search when FTS5 unavailable
- **Ranking metadata foundation** — FTS results return `timestamp`, `person_id`, `conversation_id`, `project_id` for future reranking

#### Changed

- `MessageRepository.delete()` nulls out `memories.source_message_id` and `memory_versions.source_message_id` before deleting
- `delete_conversation` endpoint nulls out FK references before deleting messages
- `merge_people` now reassigns `conversation_participants` before deleting source person
- Conversation model: `cascade="all, delete-orphan"` on `messages` and `participants` relationships
- All foreign keys now have explicit `ondelete` behavior in ORM models

#### Security

- FTS5 operator injection blocked by query sanitization layer
- SQL injection in search parameters prevented by parameterized queries
- Project isolation verified across FTS5 searches
- Oversized query strings handled safely (422 or bounded results)

#### Testing

- Backend tests: 293/293 pass (260 original + 33 new Phase 1 tests)
- New test classes: `TestFKEnforcement`, `TestFTS5`, `TestMigration`, `TestDatabaseIntegrity`, `TestLargeData`, `TestSecurity`, `TestSearchCompatibility`, `TestCompositeIndexes`, `TestBackendImports`

### V3.3 Phase 2 — Query Optimization, Dead-Code Audit & Retrieval Foundation

#### Fixed

- **FTS5 schema fix** — removed `message_id UNINDEXED` column from FTS5 table that blocked `REBUILD` command (column name mismatch with source table `messages.id`)
- **FTS5 trigger schema fix** — all 3 sync triggers (`messages_fts_ai`, `messages_fts_ad`, `messages_fts_au`) updated to match corrected FTS5 DDL
- **FTS5 rebuild validation** — `INSERT INTO messages_fts(messages_fts) VALUES('rebuild')` now works correctly

#### Added

- **2 composite indexes** — `ix_conversations_fingerprint` (import dedup) and `ix_persons_project_id` (project stats), both verified via EXPLAIN QUERY PLAN
- **FTS5 security hardening** — expanded sanitization strips `-`, `+`, `=`, `|`, `<>`, `[]`, `;` operators; max 8 terms × 100 chars per term

#### Removed (dead code)

- `app/ai/prompts_legacy.py` — superseded by `app/ai/prompts/` package
- `app/services/chat/` subpackage — 4 unused files (`person_identity.py`, `memory_prompt.py`, `conversation_context.py`, `response_style.py`)
- `MessageRepository.fts_count()` — never called
- `MemoryVersionRepository.delete_for_memory()` — never called
- `detect_conversations()` — never called (sibling `detect_participants()` is used)
- `Metrics.record()` — never called
- `ConflictError` exception class — never raised
- Unused imports: `logging` in `factory.py` and `import_export.py`, `StyleService` in `people.py`, `MemoryVersionOut`/`to_memory_version_out` in `projects.py`, `Iterable` in `text.py`
- Dead module-level variable: `settings = get_settings()` in `config.py`
- Redundant re-import: `ConversationParticipantOut` inside `list_participants()` in `chat.py`

#### Verified

- EXPLAIN QUERY PLAN audit: all 15 query paths use intended indexes (2 new indexes added, LIKE content scan expected for 1506 rows)
- FTS5 rebuild: works on production database copy
- FTS5 triggers: INSERT, DELETE, UPDATE all verified
- Project isolation: FTS5 + all API endpoints enforce project_id filtering
- Performance: all 15 query paths sub-2ms p95 at 1506 messages
- Fallback chains: circuit breaker, provider fallback, vector→lexical, FTS5→LIKE all verified

#### Testing

- Backend tests: 293/293 pass (382s)
- Frontend typecheck: PASS
- Frontend build: PASS (207.83 KB JS, gzip: 62.65 KB)
- 10,000-message import test passes (<60s)
- FTS search on 10k messages completes in <5s

### V3.3 Phase 3 — Backup, Recovery, Summarization & Memory Relationships

#### Added

- **Backup service** — atomic backups using SQLite's online backup API, timestamped naming, integrity-checked
- **Backup validation** — comprehensive checks: file exists, readable, opens as SQLite, integrity_check, foreign_key_check, required tables, row counts
- **Backup restore** — guarded operation with emergency backup creation, in-place restore via SQLite backup API, validation after restore
- **Backup API** — `POST /backup/create`, `GET /backup`, `POST /backup/validate`, `POST /backup/restore` with path traversal protection
- **Conversation summaries** — `ConversationSummary` model with bounded heuristic summarization, rolling update strategy
- **Summarization API** — `GET /summaries/{id}`, `POST /summaries/generate`, `DELETE /summaries/{id}`
- **Summarization safety** — prompt injection defense strips system-instruction-like content before summarization
- **Memory relationships** — `MemoryRelationship` model with 6 types: supports, contradicts, supersedes, related_to, derived_from, clarifies
- **Memory relationship API** — `POST /memory-relationships`, `GET /memory-relationships/{id}`, `GET /memory-relationships/project/{id}`, `DELETE /memory-relationships/{id}`
- **Project isolation** — cross-project relationships rejected at service layer, all queries scoped by project_id
- **Contradiction handling** — preserves original memory, creates supersedes relationship (never silently deletes)
- **49 new tests** — backup creation/validation/restore/recovery, summarization, memory relationships, contradiction handling, model tests

#### Changed

- New ORM tables: `conversation_summaries`, `memory_relationships`
- Factory registers 3 new routers: backup, summaries, memory_relationships

#### Security

- Backup path traversal protection: paths validated to stay within backup directory
- Summarization strips prompt injection patterns from conversation content
- No secrets exposed in backup metadata

#### Testing

- Backend tests: 342/342 pass (293 original + 49 new Phase 3 tests)
- Frontend typecheck: PASS
- Frontend build: PASS (207.83 KB JS, gzip: 62.65 KB)
- Database integrity: ok, 0 FK violations
- New tables created: conversation_summaries, memory_relationships

### V3.3 Phase 4 — Playwright Browser E2E & Full-System Certification

#### Added

- **Playwright E2E test suite** — 61 tests across 13 spec files (smoke, projects, people, conversations, search, import, memory, chat, backup, security, isolation, relationships, summary, console-performance)
- **Playwright configuration** — Chromium project, webServer config for backend (port 8000) and frontend (port 5173), shared test fixtures
- **Test fixtures** — `waitForApp()`, `apiGet/Post/Delete`, `createProject` helpers for consistent E2E test setup
- **Console/network audit** — tests verify no console errors, no secret leakage in requests, no 5xx failures on frontend load
- **Browser performance benchmarks** — page load (<15s), search API (<2s), import API (<5s), backup API (<5s), chat API (best-effort)
- **Project isolation E2E** — verifies search does not leak across projects with timestamp-unique markers
- **Import E2E** — JSON API, CSV multipart upload, TXT multipart upload, participant preservation
- **Backup E2E** — create, list, validate, integrity check, path traversal rejection

#### Verified

- Playwright E2E: 57 passed, 4 skipped (`BLOCKED_EXTERNAL_DEPENDENCY`: OpenRouter provider timeout), 0 failed
- Backend regression: 342/342 pass (unchanged)
- Console audit: 0 errors, 0 secret leakage
- Performance: page load 2.6s avg, search 45ms avg, import 67ms avg, backup 535ms avg
- Project isolation: verified with timestamp-unique markers (no cross-project data leak)

---

## [3.2.0] - 2026-09-21

Production hardening and release certification.

### Added

- **ConversationParticipant model** — explicit ME/OTHER participant mapping per conversation
- **Participant backfill migration** — detects distinct senders from messages, creates ME/OTHER participants, assigns message `person_id`
- **Message ownership tracking** — `person_id` on every message, linked to conversation participants
- **`message_origin` field** — distinguishes `live_user`, `generated`, and `imported` messages
- **Provider circuit breaker** — `CLOSED`/`OPEN`/`HALF_OPEN` states, 5-failure threshold, 60-second cooldown, integrated into OpenRouter provider
- **Frontend error classification** — typed `ErrorCategory` (NETWORK_ERROR, PROVIDER_ERROR, RATE_LIMITED, etc.)
- **Request cancellation** — `AbortController` on project/person switch, stale-request epoch protection
- **Conversation search UI** — project-scoped search input in ChatShell
- **Paginated message retrieval** — `GET /messages` returns `{items, total, limit, offset}`, frontend loads 200 initially with "Load older messages"
- **Export project scoping** — all `/export/*` endpoints accept optional `project_id` query parameter
- **Fingerprint-based conversation dedup** — SHA-256 hash from project, source, participants, timestamps, message count, samples
- **Security regression tests** — prompt injection, project isolation, cross-project export, secret leakage
- **Circuit breaker tests** — 9 tests covering state transitions, thresholds, timeout recovery
- **Fingerprint dedup tests** — 3 tests covering exact dupes, renamed dupes, different content
- **V3.2 certification test suite** — 25 automated tests covering identity, project isolation, import, dedup, AI, reliability, performance

### Changed

- Import service creates `ConversationParticipant` records for all detected senders
- Migration enhanced: partial backfill for conversations with ME but missing OTHER participants
- Export service methods accept `project_id` filter
- ChatShell loads 200 messages initially instead of all messages
- OpenRouter provider returns clear error when circuit breaker is open
- Bounded retries: 3 for chat, 10 for embeddings, exponential backoff

### Fixed

- Chat messages now set `message_origin` (`live_user` for user, `generated` for assistant)
- Export endpoints fixed Pydantic `Optional[int]` forward reference error
- Migration backfill logic handles partially-backfilled conversations

### Security

- Prompt injection content stored as data, never interpreted as instructions
- SQLAlchemy parameterized queries prevent SQL injection
- React escapes output preventing XSS
- API keys never logged or exposed in responses/exports
- Export endpoints scoped by `project_id`
- ZIP/path traversal protection on import
- Project isolation verified across all endpoints

### Performance

- Backend startup: ~11s (includes OpenRouter initialization)
- Health endpoint: 107ms avg
- Project list: 250ms avg
- People list: 39ms avg
- Conversation list: 14ms avg
- Messages (200): 34ms avg
- Search: 44ms avg
- Import (100 messages): 184ms

### Testing

- Backend tests: 260/260 pass
- Frontend typecheck: PASS
- Frontend build: PASS (207.83 KB JS, gzip: 62.65 KB)
- Production database integrity: verified (0 NULL person_id, 0 orphans, 0 FK violations)

### Known Limitations

- No browser E2E testing (blocked: no browser automation in certification environment)
- No automated backup/recovery — database backup is manual
- Jitter not implemented on retry backoff
- Imported messages are immutable — no revision history for imported content

---

## [1.0.0] - 2026-09-21

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
