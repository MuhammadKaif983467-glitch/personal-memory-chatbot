# Contributing

Thank you for your interest in contributing to the Personal Memory Chatbot.

## Development Setup

1. Fork and clone the repository
2. Follow the [installation instructions](docs/INSTALLATION.md)
3. Create a feature branch from `master`

```powershell
git checkout -b feat/your-feature
```

## Branch Strategy

- `master` — stable release branch
- `feat/*` — new features
- `fix/*` — bug fixes
- `docs/*` — documentation changes
- `test/*` — test additions or improvements

## Coding Standards

### Python

- Python 3.10+ compatible
- Type hints on all public functions
- Docstrings on public methods
- Follow existing code patterns
- No `print()` statements in production code (use `logging`)

### TypeScript

- Strict TypeScript
- No `any` types where avoidable
- Follow existing component patterns
- Components in `components/<feature>/` directories

### General

- One file = one clear responsibility
- No comments unless asked
- No secrets or API keys in source code
- No `TODO` or `FIXME` in committed code unless intentional

## Backend Testing

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

All tests must pass before submitting a PR. Do not weaken tests.

## Frontend Verification

```powershell
cd frontend
npm run typecheck
npm run build
```

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat: add new feature
fix: correct bug
docs: update documentation
refactor: restructure code
test: add tests
security: address vulnerability
perf: improve performance
release: version bump
```

## Pull Request Expectations

1. All tests pass
2. Frontend typecheck passes
3. Frontend build succeeds
4. No secrets or credentials in the diff
5. Documentation updated if needed
6. Single responsibility per PR
7. Clear description of changes

## Security Expectations

- Never commit API keys, tokens, or credentials
- Report security vulnerabilities via [GitHub Security Advisories](https://github.com/MuhammadKaif983467-glitch/personal-memory-chatbot/security/advisories/new)
- Review imported content handling for injection risks
- Maintain project isolation across all changes
