@echo off
REM =============================================================================
REM  Smart Evacuation System — First-Time Setup Script (Windows)
REM  Run this once on a new machine. It installs everything and starts the app.
REM  Requirements: Python 3.10+, Node.js 18+
REM =============================================================================
setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0..

echo.
echo ============================================
echo   Smart Evacuation System — Setup
echo ============================================
echo.

REM ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    echo         Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v found

REM ── Check Node.js ─────────────────────────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo [OK] Node.js %%v found

echo.
echo [1/4] Setting up Python virtual environment...
if not exist "%ROOT%\.venv" (
    python -m venv "%ROOT%\.venv"
    echo       Created .venv
) else (
    echo       .venv already exists, skipping.
)

echo.
echo [2/4] Installing Python dependencies...
call "%ROOT%\.venv\Scripts\pip" install -q --upgrade pip
call "%ROOT%\.venv\Scripts\pip" install -q -r "%ROOT%\backend\requirements.txt"
echo       Done.

echo.
echo [3/4] Installing Node.js dependencies...
if not exist "%ROOT%\artifacts\evacuation-dashboard\node_modules" (
    cd /d "%ROOT%\artifacts\evacuation-dashboard"
    call npm install --silent
    echo       Done.
) else (
    echo       node_modules already exists, skipping.
)

echo.
echo [4/4] Starting servers...
echo       Backend  → http://localhost:8080
echo       Frontend → http://localhost:5173
echo.

start "Smart Evacuation - Backend" cmd /k "cd /d %ROOT% && .venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --app-dir backend"
timeout /t 3 /nobreak >nul
start "Smart Evacuation - Frontend" cmd /k "cd /d %ROOT%\artifacts\evacuation-dashboard && npm run dev"

echo.
echo ============================================
echo   Setup complete!
echo   Open http://localhost:5173 in your browser
echo ============================================
echo.
echo Both servers are starting in separate windows.
echo You can close this window now.
echo.
pause
