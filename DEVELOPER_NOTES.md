# Smart Evacuation System — Developer Notes

AI-Based Smart Evacuation System with Predictive Congestion Analysis and Dynamic Route Optimization — a research prototype inspired by Ibrahim et al., IEEE Access 2023.

## Running the Project

### Backend (FastAPI)
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Frontend (React + Vite)
```bash
cd artifacts/evacuation-dashboard
npm install     # or: pnpm install
npm run dev     # starts on http://localhost:5173
```

### All-in-one (Windows)
```cmd
scripts\run_local.bat
```

### All-in-one (Linux / macOS)
```bash
chmod +x scripts/run_local.sh
./scripts/run_local.sh
```

## Stack

- **Node.js** 18+, TypeScript 5
- **Backend:** Python 3.10+, FastAPI, uvicorn, SQLite
- **Frontend:** React 18, Vite, Tailwind CSS v4, TanStack Query, Wouter
- **API contracts:** OpenAPI 3.1 in `lib/api-spec/openapi.yaml`
- **Python packages:** fastapi, uvicorn, pydantic v2, numpy, scikit-learn, xgboost

## Architecture

The Python FastAPI backend runs on port **8080** (at path `/api/`).
The React frontend runs on port **5173** and proxies `/api` requests to the backend.

## Module Status

| Module | Status | Description |
|--------|--------|-------------|
| 1 — Layout Parser & Grid Map | ✅ Done | 3 sample layouts, JSON schema input, SQLite persistence |
| 2 — Crowd Simulation Engine | ✅ Done | Agent-based Moore neighbourhood simulation |
| 3 — Synthetic Dataset Generator | ✅ Done | 300 runs × varied params → ~500K rows CSV |
| 4 — ML Training | ✅ Done | Random Forest, XGBoost, MLP — RMSE/MAE/R² |
| 5 — Prediction + Route Optimizer | ✅ Done | Effective-path-length routing with ML predictions |
| 6 — Backend API | ✅ Done | FastAPI REST endpoints for all modules |
| 7 — Frontend Dashboard | ✅ Done | React multi-tab dashboard |
| 8 — Evaluation Suite | ✅ Done | A/B: greedy baseline vs ML-guided |

## Where Things Live

- `backend/` — Python FastAPI application
  - `backend/app/main.py` — FastAPI entry point
  - `backend/app/modules/` — Core algorithm modules
  - `backend/app/routes/` — REST route handlers
  - `backend/data/` — SQLite DB + generated files
- `lib/api-spec/openapi.yaml` — OpenAPI 3.1 spec
- `lib/api-client-react/` — React Query hooks
- `artifacts/evacuation-dashboard/` — React frontend

## Design Notes

- Production-quality research prototype, not a toy demo
- Dataset schema, model I/O, API, and dashboard are internally consistent
- Grid resolution: 30 cm/cell (matching the IEEE paper)
