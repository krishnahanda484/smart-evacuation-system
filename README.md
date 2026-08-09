# AI-Based Smart Evacuation System
### Predictive Congestion Analysis and Dynamic Route Optimization

A full research prototype implementing the system described in:

> Ibrahim, A. et al. "AI-Based Smart Evacuation System with Predictive Congestion Analysis and Dynamic Route Optimization." *IEEE Access*, 2023.

This prototype replaces the paper's Monte Carlo forecasting loop with a trained ML model (XGBoost/Random Forest/MLP), enabling real-time guidance updates in microseconds rather than seconds.

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- pnpm (`npm install -g pnpm`) or npm (included with Node.js)

### Run (Linux / macOS)
```bash
chmod +x scripts/run_local.sh
./scripts/run_local.sh
```

### Run (Windows)
```cmd
scripts\run_local.bat
```

### Run manually (step by step)
1. `python -m venv .venv && .venv\Scripts\activate` — create virtual environment
2. `pip install -r backend\requirements.txt` — install Python packages
3. `cd artifacts\evacuation-dashboard && npm install` — install Node packages
4. `uvicorn app.main:app --port 8080 --app-dir backend` — start backend
5. `cd artifacts\evacuation-dashboard && npm run dev` — start frontend

Both scripts:
1. Create a Python virtual environment and install dependencies
2. Generate the synthetic training dataset (~5 min, runs once)
3. Train the ML models (~2 min, runs once)
4. Start the backend API on `http://localhost:8080`
5. Start the frontend dashboard on `http://localhost:5173`

---

## Architecture

```
┌─────────────────────────────────────────────┐
│            React Dashboard (Vite)            │
│         artifacts/evacuation-dashboard/      │
│  Tab 1: Grid Map  │ Tab 2: Simulation        │
│  Tab 3: Pipeline  │ Tab 4: Evaluation        │
└──────────────┬──────────────────────────────┘
               │ REST /api/*
┌──────────────▼──────────────────────────────┐
│         FastAPI Backend (Python 3.11)        │
│              backend/                        │
│  Module 1: Layout Parser & Grid Map          │
│  Module 2: Crowd Simulation Engine           │
│  Module 3: Synthetic Dataset Generator       │
│  Module 4: ML Training (RF / XGBoost / MLP)  │
│  Module 5: Congestion Predictor + Router     │
│  Module 6: REST API                          │
│  Module 8: Evaluation Suite                  │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│         SQLite  (backend/data/)              │
│  layouts · simulation_runs · ml_models       │
└─────────────────────────────────────────────┘
```

---

## Modules

| # | Module | Location | Description |
|---|--------|----------|-------------|
| 1 | Layout Parser & Grid Map | `backend/app/modules/grid_map.py` | Builds 30 cm/cell discrete grids; 3 sample layouts |
| 2 | Crowd Simulation Engine | `backend/app/modules/simulation.py` | Agent-based, Moore neighbourhood, N(1.34,0.26) m/s speed |
| 3 | Synthetic Dataset Generator | `backend/app/modules/dataset_gen.py` | 300 runs × varied params → ~500K rows CSV |
| 4 | ML Training | `backend/app/modules/ml_train.py` | Random Forest, XGBoost, MLP — RMSE/MAE/R² comparison |
| 5 | Congestion Predictor + Router | `backend/app/modules/predictor.py` | Effective-path-length routing with ML predictions |
| 6 | Backend API | `backend/app/routes/` | FastAPI REST endpoints for all modules |
| 7 | Frontend Dashboard | `artifacts/evacuation-dashboard/` | React + Vite + Recharts multi-tab dashboard |
| 8 | Evaluation Suite | `backend/app/modules/evaluation.py` | A/B: greedy baseline vs ML-guided (target: ~21% improvement) |
| 9 | Packaging | `scripts/`, `README.md` | Run scripts, ZIP archive |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/healthz` | Health check |
| GET | `/api/layouts` | List all layouts |
| POST | `/api/layouts` | Create custom layout |
| GET | `/api/layouts/{id}` | Get layout with grid |
| POST | `/api/simulation/start` | Start simulation run |
| POST | `/api/simulation/{id}/step` | Advance N steps |
| GET | `/api/simulation/{id}/state` | Poll live state |
| POST | `/api/simulation/{id}/run` | Run to completion |
| GET | `/api/simulation/{id}/results` | Full results |
| GET | `/api/dataset/status` | Dataset generation status |
| POST | `/api/dataset/generate` | Start dataset generation |
| GET | `/api/dataset/download` | Download CSV |
| GET | `/api/ml/status` | ML training status |
| POST | `/api/ml/train` | Start training |
| GET | `/api/ml/metrics` | Model comparison table |
| GET | `/api/ml/writeup` | Auto-generated paper writeup |
| POST | `/api/evaluation/run` | Start A/B evaluation |
| GET | `/api/evaluation/results` | Evaluation results |

Interactive docs: `http://localhost:8080/docs`

---

## Cell Types

| Value | Name | Colour | Meaning |
|-------|------|--------|---------|
| 0 | FREE | #F0F0F0 | Passable floor |
| 1 | WALL | #2D3748 | Structural wall |
| 2 | OBSTACLE | #805AD5 | Furniture / equipment |
| 3 | EXIT | #38A169 | Emergency exit |

Grid resolution: **30 cm/cell** (matching the reference paper).

---

## Dataset & ML

The synthetic dataset is generated by running the simulation 300 times across:
- 3 layouts (small classroom / medium office / large mall)
- 5 population levels (5%–60% of passable area)
- 4 adherence rates (0.30, 0.50, 0.70, 0.90)
- 5 replications per combination

**Features**: local density, exit proximity, walking speed, exit flow rate, population, timestamp  
**Labels**: `congestion_in_30s` (primary), `evacuation_time_s` (secondary)

Three models are compared and the best by test-set RMSE is saved as the production predictor.

---

## Evaluation

The evaluation suite runs N simulations (default 20) under:
- **Greedy baseline**: every agent always moves to their nearest exit
- **ML-guided**: every 30 s, the route optimizer recomputes effective path lengths using ML-predicted congestion; guided agents (ρ fraction) update their target exit

The benchmark is **~21% mean evacuation time reduction** (Ibrahim et al., 2023).

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── database.py              # SQLite schema + CRUD
│   │   ├── models/schemas.py        # Pydantic models
│   │   ├── modules/
│   │   │   ├── grid_map.py          # Module 1
│   │   │   ├── sample_layouts.py    # 3 built-in layouts
│   │   │   ├── simulation.py        # Module 2
│   │   │   ├── dataset_gen.py       # Module 3
│   │   │   ├── ml_train.py          # Module 4
│   │   │   ├── predictor.py         # Module 5
│   │   │   └── evaluation.py        # Module 8
│   │   └── routes/
│   │       ├── layouts.py
│   │       ├── simulation.py
│   │       ├── dataset.py
│   │       ├── ml.py
│   │       └── evaluation.py
│   ├── data/                        # SQLite DB + generated files (gitignored)
│   └── requirements.txt
├── artifacts/evacuation-dashboard/  # React frontend (Module 7)
├── lib/api-spec/openapi.yaml        # OpenAPI 3.1 spec
├── lib/api-client-react/            # Orval-generated React Query hooks
├── scripts/
│   ├── run_local.sh                 # Linux/macOS launcher
│   └── run_local.bat                # Windows launcher
└── README.md
```

---

## Reference

Ibrahim, A., Al-Shaibani, A., Al-Khateeb, H., & Epiphaniou, G. (2023).
*AI-Based Smart Evacuation System with Predictive Congestion Analysis and Dynamic Route Optimization.*
IEEE Access. https://doi.org/10.1109/ACCESS.2023.XXXXXXX
