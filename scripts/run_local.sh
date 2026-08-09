#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Smart Evacuation System — local run script (Linux / macOS)
# Requires: Python 3.11+, Node.js 20+, pnpm 9+
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── 1. Python virtual environment ─────────────────────────────────────────────
VENV="$ROOT/.venv"
if [ ! -d "$VENV" ]; then
  echo "[setup] Creating Python venv…"
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

echo "[setup] Installing Python dependencies…"
pip install -q -r "$ROOT/backend/requirements.txt"

# ── 2. Node dependencies ──────────────────────────────────────────────────────
echo "[setup] Installing Node.js dependencies…"
cd "$ROOT" && pnpm install --frozen-lockfile

# ── 3. Generate dataset (if not present) ─────────────────────────────────────
DATASET="$ROOT/backend/data/simulation_dataset.csv"
if [ ! -f "$DATASET" ]; then
  echo "[data]  Generating synthetic dataset (~5 min)…"
  python3 - <<'EOF'
import sys; sys.path.insert(0, "backend")
from app.modules.dataset_gen import generate_dataset
generate_dataset()
print("Dataset generation complete.")
EOF
else
  echo "[data]  Dataset found, skipping generation."
fi

# ── 4. Train models (if not present) ─────────────────────────────────────────
MODEL="$ROOT/backend/data/best_congestion_model.pkl"
if [ ! -f "$MODEL" ]; then
  echo "[ml]    Training ML models (~2 min)…"
  python3 - <<'EOF'
import sys; sys.path.insert(0, "backend")
from app.modules.ml_train import train_models
result = train_models()
print(f"Training complete. Best model: {result['best_congestion']}")
EOF
else
  echo "[ml]    Trained models found, skipping training."
fi

# ── 5. Launch services ────────────────────────────────────────────────────────
echo ""
echo "Starting backend API on  http://localhost:8080"
echo "Starting frontend on     http://localhost:5173"
echo "Press Ctrl-C to stop both."
echo ""

trap 'kill 0' INT TERM

# Backend
cd "$ROOT"
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --app-dir backend &
BACKEND_PID=$!

# Frontend (Vite dev server with API proxy to localhost:8080)
cd "$ROOT/artifacts/evacuation-dashboard"
VITE_API_URL=http://localhost:8080 pnpm dev --port 5173 &
FRONTEND_PID=$!

wait $BACKEND_PID $FRONTEND_PID
