# Screenshot Plan

**Status:** TODO — Screenshots will be captured from a live running instance.

---

## Recommended Screenshots (6)

---

### 1. Main Chat Interface

| Field | Value |
|-------|-------|
| **Screen** | Chat page with active conversation |
| **Purpose** | Show the primary user experience |
| **Viewport** | 1280x800 (standard laptop) |
| **Should be visible** | Conversation rail (left), message bubbles, composer, confidence badges, source evidence panel, connection status (green), project selector |
| **Should NOT be visible** | API keys, `.env` contents, database file paths, raw SQL queries, terminal with secrets |
| **Privacy checks** | No real names in sample data, no API keys in UI, no personal data visible |

---

### 2. Project & Person Setup

| Field | Value |
|-------|-------|
| **Screen** | People page with project selector open |
| **Purpose** | Show the two-person project model |
| **Viewport** | 1280x800 |
| **Should be visible** | Project list, "+ New" button, person cards with ME/OTHER roles, participant counts |
| **Should NOT be visible** | Default project ID numbers, raw database IDs, internal routing |
| **Privacy checks** | Use generic names (e.g., "Person A", "Person B"), no real conversation data |

---

### 3. Memory Timeline

| Field | Value |
|-------|-------|
| **Screen** | Memories page with filter and version history |
| **Purpose** | Show memory system with versioning |
| **Viewport** | 1280x800 |
| **Should be visible** | Memory list with types/confidence, filter controls, version history panel, source message links |
| **Should NOT be visible** | Memory IDs, internal confidence formulas, raw embeddings |
| **Privacy checks** | Use generic sample memories, no real personal data |

---

### 4. Conversation Analysis

| Field | Value |
|-------|-------|
| **Screen** | People page with profile and style analysis |
| **Purpose** | Show automated analysis capabilities |
| **Viewport** | 1280x800 |
| **Should be visible** | Profile card (interests, preferences, facts), writing style (tone, vocabulary), "Run analysis" button |
| **Should NOT be visible** | Analysis algorithm details, internal scoring weights, raw NLP output |
| **Privacy checks** | Use generic sample profiles, no real personal analysis |

---

### 5. Import Workflow

| Field | Value |
|-------|-------|
| **Screen** | Import page with preview showing |
| **Purpose** | Show safe import workflow with preview |
| **Viewport** | 1280x800 |
| **Should be visible** | Format tabs (JSON/CSV/TXT/ZIP), file upload area, preview table, consent checkbox, Import button |
| **Should NOT be visible** | Uploaded file contents, raw parsing output, import script paths |
| **Privacy checks** | Use small generic sample file, no real conversation data in preview |

---

### 6. Settings & Connection Status

| Field | Value |
|-------|-------|
| **Screen** | Settings page |
| **Purpose** | Show configuration and security model |
| **Viewport** | 1280x800 |
| **Should be visible** | Backend health card, provider status, voice status, model configuration, connection indicator |
| **Should NOT be visible** | API key values, `.env` file contents, database connection strings, any secrets |
| **Privacy checks** | All sensitive values must show as "configured" or masked, never actual values |

---

## Capture Instructions

1. Start the application with `.\scripts\start_all.ps1`
2. Use sample/regression data (not real personal data)
3. Open browser at http://localhost:5173
4. Capture each screenshot at 1280x800 viewport
5. Save to `docs/screenshots/` directory
6. Name files: `dashboard.png`, `chat.png`, `memories.png`, `people.png`, `import.png`, `settings.png`
7. Verify no secrets or personal data are visible before committing

---

## Privacy Checklist

- [ ] No API keys visible in any screenshot
- [ ] No `.env` file contents visible
- [ ] No real personal names used
- [ ] No real conversation data displayed
- [ ] No database file paths shown
- [ ] No internal IDs prominently displayed
- [ ] All sample data is generic/placeholder
