@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM Smart Evacuation System — local run script (Windows)
REM Requires: Python 3.11+, Node.js 20+, pnpm 9+
REM ─────────────────────────────────────────────────────────────────────────────
setlocal ENABLEDELAYEDEXPANSION

set ROOT=%~dp0..

REM ── 1. Python venv ─────────────────────────────────────────────────────────
if not exist "%ROOT%\.venv" (
    echo [setup] Creating Python venv...
    python -m venv "%ROOT%\.venv"
)
call "%ROOT%\.venv\Scripts\activate.bat"

echo [setup] Installing Python dependencies...
pip install -q -r "%ROOT%\backend\requirements.txt"

REM ── 2. Node dependencies ────────────────────────────────────────────────────
echo [setup] Installing Node.js dependencies...
cd /d "%ROOT%\artifacts\evacuation-dashboard"
call pnpm install

REM ── 3. Generate dataset ──────────────────────────────────────────────────────
if exist "%ROOT%\backend\data\simulation_dataset.csv" goto skip_data
echo [data]  Generating synthetic dataset (~5 min)...
cd /d "%ROOT%"
python -c "import sys; sys.path.insert(0,'backend'); from app.modules.dataset_gen import generate_dataset; generate_dataset(); print('Done.')"
goto done_data
:skip_data
echo [data]  Dataset found, skipping.
:done_data

REM ── 4. Train models ──────────────────────────────────────────────────────────
goto skip_ml
if exist "%ROOT%\backend\data\best_congestion_model.pkl" goto skip_ml
echo [ml]    Training ML models (~2 min)...
cd /d "%ROOT%"
python -c "import sys; sys.path.insert(0,'backend'); from app.modules.ml_train import train_models; r=train_models(); print('Best:',r['best_congestion'])"
goto done_ml
:skip_ml
echo [ml]    Models found, skipping.
:done_ml

REM ── 5. Start services in separate windows ────────────────────────────────────
echo.
echo Starting backend on http://localhost:8080 ...
start "Evacuation API" cmd /k "cd /d %ROOT% && .venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --app-dir backend"

echo Starting frontend on http://localhost:5173 ...
start "Evacuation Dashboard" cmd /k "cd /d %ROOT%\artifacts\evacuation-dashboard && set VITE_API_URL=http://localhost:8080 && pnpm dev --port 5173"

echo.
echo Both services started in separate windows.
echo Open http://localhost:5173 in your browser.
pause
