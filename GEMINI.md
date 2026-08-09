# Smart Evacuation System

AI-Based Smart Evacuation System with Predictive Congestion Analysis and Dynamic Route Optimization.
Research prototype based on Ibrahim et al., IEEE Access 2023.

## Project Overview

This is a **full-stack ML research system** with:
- **Backend**: Python FastAPI on port 8080
- **Frontend**: React + Vite dashboard on port 5173
- **ML Pipeline**: Random Forest / XGBoost / MLP congestion prediction
- **Simulation**: Agent-based crowd evacuation engine

## Quick Start (use these exact commands)

### Step 1 - Install and Start (first time on a new system)
Run from the project root directory:
```
scripts\setup.bat
```

### Step 2 - Start servers (already installed)
Run from the project root directory:
```
scripts\run_local.bat
```

### Manual start (if bat files do not work)
Terminal 1 - Backend:
```
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --app-dir backend
```
Terminal 2 - Frontend:
```
cd artifacts\evacuation-dashboard
npm run dev
```

### Linux or macOS:
```
bash scripts/run_local.sh
```

## Service URLs
- Dashboard UI: http://localhost:5173
- API (FastAPI): http://localhost:8080
- API Docs (Swagger): http://localhost:8080/docs

## Prerequisites
- Python 3.10 or higher
- Node.js 18 or higher
- npm (bundled with Node.js)

## Project Structure
```
smart_evacuation_system/
├── backend/                         Python FastAPI backend
│   ├── app/
│   │   ├── main.py                  Entry point
│   │   ├── modules/
│   │   │   ├── simulation.py        Core agent-based simulation
│   │   │   ├── ml_train.py          ML model training
│   │   │   ├── predictor.py         Real-time congestion prediction
│   │   │   ├── dataset_gen.py       Training data generator
│   │   │   ├── evaluation.py        A/B evaluation suite
│   │   │   ├── grid_map.py          Building layout model
│   │   │   └── sample_layouts.py    3 built-in layouts
│   │   └── routes/                  REST API endpoints
│   ├── data/                        SQLite DB + ML models (auto-generated)
│   └── requirements.txt
├── artifacts/evacuation-dashboard/  React frontend
├── scripts/
│   ├── setup.bat                    First-time setup (Windows)
│   ├── run_local.bat                Start both servers (Windows)
│   └── run_local.sh                 Start both servers (Linux/macOS)
├── GEMINI.md                        This file (Antigravity config)
└── README.md
```

## 4 Tabs in the Dashboard
1. Grid Map - View/edit building floor plans, create custom layouts
2. Simulation - Run live evacuation with ML-guided routing
3. Pipeline - Generate training data, Train ML models, Reload predictor
4. Evaluation - A/B test ML-guided vs greedy baseline (target ~21% improvement)

## Troubleshooting
- If backend fails: check Python 3.10+ is installed (python --version)
- If frontend fails: check Node 18+ is installed (node --version)
- If port 8080 in use: kill the process using it
- If ML routing not working: go to Pipeline tab, Generate Dataset, Train Models, Reload Predictor
- Backend logs: check the terminal window titled "Smart Evacuation - Backend"
- Frontend logs: check the terminal window titled "Smart Evacuation - Frontend"

## Agent Instructions
When the user says "make it live", "start the project", or "run it":
1. Start backend as daemon from project root: .venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --app-dir backend
2. Start frontend as daemon from artifacts\evacuation-dashboard: npm run dev
3. Tell the user to open http://localhost:5173

When the user says "set it up" or "install" on a new system:
1. Create venv: python -m venv .venv
2. Install Python deps: .venv\Scripts\pip install -r backend\requirements.txt
3. Install Node deps: cd artifacts\evacuation-dashboard then npm install
4. Then start both servers as above
