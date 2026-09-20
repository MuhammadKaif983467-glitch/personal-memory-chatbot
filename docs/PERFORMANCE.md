# Performance

Measured performance results for the Personal Memory Chatbot v3.2.0.

These measurements were taken during the v3.2.0 certification process using the test database with local SQLite and OpenRouter provider. Actual performance will vary based on hardware, database size, and provider latency.

## Measurements

| Operation | p50 | Notes |
|-----------|-----|-------|
| Backend startup | ~11s | Includes OpenRouter initialization and embedding compatibility check |
| Health endpoint | 107ms | Provider status and data counts |
| Project list | 250ms | Includes per-project statistics |
| People list | 39ms | Per-person message counts |
| Conversation list | 14ms | Lightweight listing |
| Messages (200) | 34ms | Paginated retrieval |
| Search | 44ms | Unified search across messages, memories, conversations |
| Import (100 messages) | 184ms | Includes memory extraction |

## Environment

- Platform: Windows 10/11
- Database: SQLite (local file)
- Backend: FastAPI + Uvicorn (single worker)
- Provider: OpenRouter (external API)

## Notes

- Backend startup includes OpenRouter provider initialization and embedding compatibility verification
- Import time includes memory extraction and embedding generation
- Chat round-trip time depends on provider response latency (not measured in certification)
- Project list time includes computing per-project statistics (memory count, message count, etc.)
- All measurements taken with the test database containing ~1400 messages and ~5000 memories

## Scaling Considerations

- SQLite performance degrades with very large databases (>100k messages)
- Vector retrieval scales linearly with the number of active memories
- Import time scales linearly with the number of messages
- Memory extraction runs during import, not during chat
- Paginated message retrieval prevents large payload issues
