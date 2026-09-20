# Demo Script

**Duration:** 3-5 minutes
**Audience:** Software engineers, recruiters, technical interviewers
**Setup:** Application running (backend on localhost:8000, frontend on localhost:5173)

---

## Step 1: Start Application (15 seconds)

**Click:** Run `.\scripts\start_all.ps1` in terminal

**Say:** "This is the Personal Memory Chatbot v1.0.0. It imports real conversation history, builds persistent memories with evidence trails, and answers questions grounded in retrieved memories. Let me show you how it works."

**Audience should understand:** One-command startup, clean architecture

---

## Step 2: Show Premium Interface (20 seconds)

**Click:** Open http://localhost:5173 in browser

**Say:** "The frontend is built with React and TypeScript. Notice the dark premium interface, the connection status indicator showing CONNECTED, and the project switcher in the sidebar."

**Point out:**
- Connection status (green = CONNECTED)
- Navigation: Chat, Memories, People, Import, Settings
- Project selector in sidebar

**Audience should understand:** Professional UI, real-time status monitoring

---

## Step 3: Create/Select Project (30 seconds)

**Click:** Click the project selector, then "+ New" button

**Say:** "Projects isolate data for different people. A two-person project has exactly two participants: ME (your side) and OTHER (the person the chatbot remembers)."

**Show:** Create a project with "Me" as ME and "Test Person" as OTHER

**Audience should understand:** Data isolation, two-person model, ME/OTHER roles

---

## Step 4: Import Conversation (45 seconds)

**Click:** Click "Import" in navigation

**Say:** "I'll import a sample conversation. The system supports JSON, CSV, TXT, and ZIP formats. Let me show the preview step first."

**Click:** Upload a sample file, show preview

**Say:** "The preview is strictly read-only. Nothing is stored until you confirm. Notice the consent checkbox — imported data is treated with explicit consent."

**Click:** Check consent, click Import

**Audience should understand:** Safe import workflow, consent model, preview step

---

## Step 5: Show Analysis (30 seconds)

**Click:** Click "People" in navigation, select the imported person

**Say:** "After import, the system analyzes the conversation to build a structured profile."

**Show:**
- Person card with message count
- Profile section (interests, preferences, facts, topics)
- Writing style section (tone, vocabulary, greetings)

**Audience should understand:** Automated analysis, structured profiles

---

## Step 6: Show Memory Timeline (30 seconds)

**Click:** Click "Memories" in navigation

**Say:** "These are the memories extracted from the conversation. Each memory has a type, confidence score, and source message link."

**Show:**
- Memory list with types (FACT, PREFERENCE, etc.)
- Confidence badges (HIGH, MEDIUM, LOW)
- Source message links
- Filter options (by type, status, search)

**Click:** Click "History" on a memory to show version trail

**Say:** "Every memory has a full revision history. If a memory is corrected, the old value is superseded — never deleted — and a new version is recorded."

**Audience should understand:** Memory versioning, evidence trails, audit capability

---

## Step 7: Ask a Historical Question (45 seconds)

**Click:** Click "Chat" in navigation, select the person

**Type:** "What does [person] prefer to eat?"

**Say:** "Watch the retrieval process. The system embeds my question, searches the vector store for relevant memories, ranks them by similarity and confidence, and builds grounded context."

**Show:**
- Reply with confidence level (HIGH/MEDIUM/LOW)
- Source memories panel (expandable)
- Debug panel showing retrieval details

**Audience should understand:** Hybrid retrieval, source citation, confidence scoring

---

## Step 8: Demonstrate Current-Conversation Learning (45 seconds)

**Type:** "I now prefer sushi over pizza"

**Say:** "The system detected an explicit statement about preferences. Watch the reply."

**Show:**
- "Learned: NEW_MEMORY" indicator in the reply
- Navigate to Memories to show the new memory

**Type:** "Actually, I changed my mind. I prefer tacos now"

**Show:**
- "Learned: CORRECTION" indicator
- Navigate to Memories to show the old memory superseded and new one created
- Show the version history linking them

**Audience should understand:** Real-time learning, correction detection, supersession

---

## Step 9: Show Connection Status (15 seconds)

**Click:** Point to the connection status indicator

**Say:** "The UI shows real-time backend connectivity: CONNECTED, DEGRADED, or OFFLINE. If the backend goes down, the user knows immediately."

**Audience should understand:** Production-ready status monitoring

---

## Step 10: Show Settings/Security (20 seconds)

**Click:** Click "Settings" in navigation

**Say:** "The settings screen shows backend health, provider status, and voice capability. Notice: no API keys are ever displayed. The system uses environment variables for all secrets."

**Show:**
- Backend health status
- Provider configuration (no keys shown)
- Voice status (architecture-only)

**Audience should understand:** Security model, secret management

---

## Step 11: Finish with Certification (15 seconds)

**Say:** "This is v1.0.0, fully certified. 174 backend tests pass. 11 live E2E acceptance tests pass. Frontend typecheck and build pass. Secret scan passes. The whole system is production-ready."

**Audience should understand:** Quality assurance, test coverage, production readiness

---

## Summary

| Step | Duration | Key Point |
|------|----------|-----------|
| Start app | 15s | One-command startup |
| Interface | 20s | Premium UI, connection status |
| Project | 30s | Two-person model, isolation |
| Import | 45s | Safe workflow, consent, preview |
| Analysis | 30s | Automated profiles |
| Memories | 30s | Versioning, evidence trails |
| Chat | 45s | Hybrid retrieval, grounding |
| Learning | 45s | Corrections, supersession |
| Status | 15s | Real-time monitoring |
| Settings | 20s | Security, no secrets |
| Certification | 15s | Quality assurance |
| **Total** | **~4 min** | |
