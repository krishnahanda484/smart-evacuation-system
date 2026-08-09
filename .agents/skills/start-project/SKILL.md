---
name: start-project
description: >
  Sets up and starts the Smart Evacuation System on any machine.
  Use this skill when the user says "make it live", "start the project",
  "run it", "set it up", or "install dependencies".
---

# Smart Evacuation System — Start/Setup Skill

## When to use this skill
- User says "make it live", "run the project", "start the servers"
- User says "set it up", "install", "fresh install", "new machine"
- Any time the backend or frontend servers need to be started

---

## CASE A: Already installed — just start the servers

Run BOTH of these as daemon background tasks (IsDaemon = true):

### Backend (run from project root)
```
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --app-dir backend
```

### Frontend (run from artifacts\evacuation-dashboard)
```
npm run dev
```

After starting, tell the user:
> Both servers are live. Open http://localhost:5173 in your browser.

---

## CASE B: Fresh install on a new system

Run these steps IN ORDER, waiting for each to complete:

### Step 1 — Create Python virtual environment
```
python -m venv .venv
```
Run from project root. Skip if .venv folder already exists.

### Step 2 — Install Python dependencies
```
.venv\Scripts\pip install -r backend\requirements.txt
```
Run from project root.

### Step 3 — Install Node.js dependencies
```
npm install
```
Run from: artifacts\evacuation-dashboard

### Step 4 — Start the servers (as in Case A above)

---

## How to verify servers are running

- Backend health check: GET http://localhost:8080/api/healthz  → should return {"status":"ok"}
- Frontend: open http://localhost:5173 in browser

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python` not found | Install Python 3.10+ from python.org |
| `npm` not found | Install Node.js 18+ from nodejs.org |
| Port 8080 in use | Run: `netstat -ano \| findstr :8080` then kill the PID |
| Port 5173 in use | Vite auto-picks next port, check terminal output |
| pip install fails | Try: `.venv\Scripts\python -m pip install --upgrade pip` first |
| npm install fails | Try: `npm cache clean --force` then retry |
| ML model missing | Go to Pipeline tab in dashboard, click Generate Dataset, then Train Models |
