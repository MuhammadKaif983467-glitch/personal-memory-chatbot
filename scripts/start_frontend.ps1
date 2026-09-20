# Personal Memory Chatbot - Frontend Startup Script
# Starts the Vite dev server on http://localhost:5173

$ErrorActionPreference = "Stop"
$FrontendDir = Join-Path $PSScriptRoot ".." "frontend"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Personal Memory Chatbot - Frontend" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Check node_modules exists
$NodeModules = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host "[INFO] Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    npm install
    Pop-Location
}

Write-Host ""
Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

Push-Location $FrontendDir
npm run dev
Pop-Location
