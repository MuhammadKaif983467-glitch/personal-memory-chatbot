# Personal Memory Chatbot - Full Stack Startup
# Starts both backend and frontend in parallel

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Personal Memory Chatbot - Full Stack" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host ""

$BackendScript = Join-Path $PSScriptRoot "start_backend.ps1"
$FrontendScript = Join-Path $PSScriptRoot "start_frontend.ps1"

# Start backend in a new window
Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$BackendScript`"" -WindowStyle Normal
Write-Host "[OK] Backend process started" -ForegroundColor Green

# Wait a moment for backend to initialize
Start-Sleep -Seconds 2

# Start frontend in a new window
Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$FrontendScript`"" -WindowStyle Normal
Write-Host "[OK] Frontend process started" -ForegroundColor Green

Write-Host ""
Write-Host "Both services are starting. Check their windows for status." -ForegroundColor Cyan
Write-Host "Backend health: http://localhost:8000/health" -ForegroundColor DarkGray
Write-Host "Frontend app:   http://localhost:5173" -ForegroundColor DarkGray
