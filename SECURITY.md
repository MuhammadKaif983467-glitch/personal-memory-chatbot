# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 3.2.0 | Yes |
| 1.0.0 | Yes |
| < 1.0.0 | No |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it via [GitHub Security Advisories](https://github.com/MuhammadKaif983467-glitch/personal-memory-chatbot/security/advisories/new).

Do **not** open a public issue for security vulnerabilities.

## Security Measures

### Secret Management

- API keys are stored in `.env` only, never in source code
- `.env` is excluded from version control via `.gitignore`
- `.env.example` contains placeholder values only
- Health and settings endpoints never expose secret values
- Error messages are sanitized before surfacing

### Prompt Injection

- Imported conversation content is treated as **data**, not instructions
- System prompt explicitly marks memories as DATA sections
- Conversation content is wrapped in quotation marks to visually separate from instructions
- Import content cannot escalate to system-level instructions

### Project Isolation

- All data is scoped by `project_id`
- People, conversations, messages, memories, and vectors are isolated per project
- Cross-project data access is prevented at the repository layer
- Export endpoints accept `project_id` filter

### Input Validation

- SQLAlchemy parameterized queries prevent SQL injection
- React escapes all output by default (XSS prevention)
- ZIP file import validates path traversal
- File uploads validated for size and content type
- Import requires explicit consent confirmation

### Database Safety

- SQLite database file excluded from version control
- Import creates conversation participants before messages
- Message ownership tracked via `person_id`
- Memory corrections create new versions rather than overwriting

## Best Practices

- Never commit `.env` or any file containing API keys
- Use split-key configuration (KEY_1 for embeddings, KEY_2 for chat)
- Rotate API keys periodically
- Use the local heuristic provider for development without API keys
- Back up the database regularly
- Review imported content before confirming consent
