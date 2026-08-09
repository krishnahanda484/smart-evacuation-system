@echo off
REM =============================================================================
REM  Smart Evacuation System — Quick Start (Windows)
REM  Assumes setup.bat has already been run once.
REM  If running for the first time, run setup.bat instead.
REM =============================================================================
setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0..

REM ── Check that .venv exists ───────────────────────────────────────────────────
if not exist "%ROOT%\.venv" (
    echo [!] Virtual environment not found.
    echo     Please run setup.bat first for first-time installation.
    echo.
    set /p CHOICE="Run setup.bat now? (Y/N): "
    if /i "!CHOICE!"=="Y" (
        call "%~dp0setup.bat"
        exit /b
    )
    pause
    exit /b 1
)

REM ── Check that node_modules exists ───────────────────────────────────────────
if not exist "%ROOT%\artifacts\evacuation-dashboard\node_modules" (
    echo [!] Node modules not found.
    echo     Please run setup.bat first for first-time installation.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Smart Evacuation System — Starting...
echo ============================================
echo   Backend  → http://localhost:8080
echo   Frontend → http://localhost:5173
echo   API Docs → http://localhost:8080/docs
echo ============================================
echo.

start "Smart Evacuation - Backend" cmd /k "cd /d %ROOT% && .venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --app-dir backend"
timeout /t 2 /nobreak >nul
start "Smart Evacuation - Frontend" cmd /k "cd /d %ROOT%\artifacts\evacuation-dashboard && npm run dev"

echo Both servers are starting in separate windows.
echo Open http://localhost:5173 in your browser.
echo.
timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"
