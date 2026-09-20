# Roadmap

Development roadmap for the Personal Memory Chatbot.

## Completed

### v3.2.0 (2026-09-21)

- Two-person project model with explicit ME/OTHER
- Multi-format import (WhatsApp, Telegram, Instagram, Facebook, JSON, CSV, TXT, ZIP)
- Universal import with automatic platform detection
- Fingerprint-based conversation deduplication
- Persistent memory with confidence and revision history
- Hybrid retrieval (vector + lexical)
- Provider circuit breaker and bounded retries
- Paginated message retrieval
- Project-scoped export
- Frontend error classification
- Request cancellation via AbortController
- Conversation search UI
- Security regression tests
- 260/260 backend tests passing

### v1.0.0 (2026-09-21)

- Initial production release
- Core memory system with extraction and versioning
- Chat with hybrid retrieval
- Import pipeline (JSON, CSV, TXT, ZIP)
- Project isolation
- OpenRouter integration
- Premium dark UI

## Planned

### v3.3 (Future)

- **Browser E2E testing** — Automated browser verification
- **Automated backup/recovery** — Scheduled database backups
- **Retry jitter** — Add jitter to exponential backoff
- **Message virtualization** — Virtual scrolling for large conversations
- **Advanced retrieval** — Reranking, multi-query, HyDE
- **Improved style matching** — Better communication style adaptation
- **Voice input/output** — Full STT/TTS integration
- **Additional import formats** — Signal, Discord, Slack
- **Deployment support** — Docker production setup, CI/CD
- **Observability** — Structured logging, metrics, tracing
- **Evaluation benchmarks** — Automated quality measurement
- **Imported-message revision history** — Track changes to imported content
- **Multi-user support** — User authentication and authorization
- **Mobile layouts** — Optimized responsive design
