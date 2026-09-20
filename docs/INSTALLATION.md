# Installation

Setup instructions for the Personal Memory Chatbot.

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Windows | 10/11 | Primary development platform |
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| npm | 8+ | Frontend package manager |
| Git | 2.30+ | Version control |
| OpenRouter API key | — | For live AI responses |

## Clone

```powershell
git clone https://github.com/MuhammadKaif983467-glitch/personal-memory-chatbot.git
cd chatbot
```

## Environment Setup

```powershell
Copy-Item .env.example .env
```

Edit `.env` and configure at minimum:

```ini
OPENROUTER_API_KEY_1=your_embedding_key
OPENROUTER_API_KEY_2=your_chat_key
```

See [CONFIGURATION.md](CONFIGURATION.md) for all available options.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

### Start Backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or use the script:

```powershell
.\scripts\start_backend.ps1
```

Backend: http://localhost:8000

API docs: http://localhost:8000/docs

## Frontend

```powershell
cd frontend
npm install
```

### Start Frontend

```powershell
npm run dev
```

Or use the script:

```powershell
.\scripts\start_frontend.ps1
```

Frontend: http://localhost:5173

## All-in-One

```powershell
.\scripts\start_all.ps1
```

## Docker

```powershell
docker-compose up
```

Note: Docker Compose configuration exists but may require additional setup for the frontend build.

## Verification

After starting, verify:

```powershell
# Backend health
Invoke-RestMethod http://localhost:8000/health

# Run backend tests
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# Frontend typecheck
cd frontend
npm run typecheck
```
