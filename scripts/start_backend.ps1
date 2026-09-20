# Personal Memory Chatbot - Backend Startup Script
# Starts the FastAPI backend on http://localhost:8000

$ErrorActionPreference = "Stop"
$BackendDir = Join-Path (Join-Path $PSScriptRoot "..") "backend"
$VenvPython = Join-Path (Join-Path (Join-Path $BackendDir ".venv") "Scripts") "python.exe"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Personal Memory Chatbot - Backend" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Check virtual environment exists
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Python virtual environment not found at $VenvPython" -ForegroundColor Red
    Write-Host "Run: cd backend && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Check database exists
$DbPath = Join-Path (Join-Path (Join-Path $PSScriptRoot "..") "data") "chatbot.db"
if (-not (Test-Path $DbPath)) {
    Write-Host "[WARN] Database not found at $DbPath - will be created on first start" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting backend on http://localhost:8000 ..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

& $VenvPython -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
