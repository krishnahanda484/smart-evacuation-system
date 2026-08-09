"""Module 6 — Simulation API routes."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..modules.grid_map import GridMap
from ..modules.simulation import EvacuationSim, DT
from ..modules.predictor import RouteOptimizer, get_predictor
from ..modules.sample_layouts import get_sample
from ..database import get_layout_row
import json

router = APIRouter(prefix="/api", tags=["simulation"])

# ── In-memory simulation store ───────────────────────────────────────────────
_sims: Dict[str, Dict[str, Any]] = {}  # run_id → {"sim": sim, "optimizer": opt, ...}
_lock = threading.Lock()


# ── Request schemas ───────────────────────────────────────────────────────────

class SimStartInput(BaseModel):
    layout_id:     str
    population:    int   = Field(ge=1, le=10000)
    adherence_rate:float = Field(default=0.70, ge=0.0, le=1.0)
    use_ml:        bool  = Field(default=True, description="Use ML-guided routing")
    seed:          Optional[int] = None


class SimStepInput(BaseModel):
    steps: int = Field(default=1, ge=1, le=200)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_gm(layout_id: str) -> GridMap:
    sample = get_sample(layout_id)
    if sample:
        return sample["grid"]
    row = get_layout_row(layout_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Layout '{layout_id}' not found.")
    raw = json.loads(row["grid_json"])
    gm = GridMap.from_dict(raw, name=row["name"], description=row["description"])
    gm.resolution_cm = row["resolution_cm"]
    return gm


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/simulation/start", status_code=201)
def start_simulation(body: SimStartInput):
    """Create and initialise a simulation run. Returns run_id."""
    gm = _load_gm(body.layout_id)
    try:
        sim = EvacuationSim(
            gm=gm,
            population=body.population,
            adherence_rate=body.adherence_rate,
            seed=body.seed,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    predictor = get_predictor() if body.use_ml else None
    optimizer = RouteOptimizer(sim, predictor) if body.use_ml else None

    run_id = f"run_{uuid.uuid4().hex[:10]}"
    with _lock:
        _sims[run_id] = {
            "sim":       sim,
            "optimizer": optimizer,
            "use_ml":    body.use_ml,
            "status":    "ready",
            "layout_id": body.layout_id,
            "population":body.population,
            "adherence": body.adherence_rate,
        }

    return {
        "run_id":     run_id,
        "status":     "ready",
        "layout_id":  body.layout_id,
        "population": body.population,
        "n_exits":    len(gm.exits),
        "n_regions":  len(sim.regions),
    }


@router.post("/simulation/{run_id}/step")
def step_simulation(run_id: str, body: SimStepInput):
    """Advance the simulation by `steps` steps. Returns latest state."""
    with _lock:
        entry = _sims.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found.")

    sim: EvacuationSim = entry["sim"]
    optimizer: Optional[RouteOptimizer] = entry["optimizer"]

    if sim.done:
        return {"state": sim.to_state_dict(), "done": True}

    for _ in range(body.steps):
        if sim.done:
            break
        sim.step()
        if optimizer and optimizer.should_update():
            rec = optimizer.recommend()
            sim.update_guided_targets(rec)

    entry["status"] = "done" if sim.done else "running"
    return {"state": sim.to_state_dict(), "done": sim.done}


@router.get("/simulation/{run_id}/state")
def get_simulation_state(run_id: str):
    """Poll current simulation state (for frontend polling)."""
    with _lock:
        entry = _sims.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found.")
    return entry["sim"].to_state_dict()


@router.post("/simulation/{run_id}/run")
def run_to_completion(run_id: str, background_tasks: BackgroundTasks):
    """Run simulation to completion in the background."""
    with _lock:
        entry = _sims.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found.")

    def _bg():
        sim: EvacuationSim = entry["sim"]
        optimizer = entry["optimizer"]
        entry["status"] = "running"
        while not sim.done and sim.step_num < 2000:
            sim.step()
            if optimizer and optimizer.should_update():
                sim.update_guided_targets(optimizer.recommend())
        entry["status"] = "done"

    background_tasks.add_task(_bg)
    return {"run_id": run_id, "message": "Running in background. Poll /state for updates."}


@router.post("/simulation/{run_id}/reset")
def reset_simulation(run_id: str):
    """Discard a simulation run."""
    with _lock:
        if run_id in _sims:
            del _sims[run_id]
    return {"deleted": run_id}


@router.get("/simulation/{run_id}/results")
def get_simulation_results(run_id: str):
    """Return full results after a completed simulation."""
    with _lock:
        entry = _sims.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found.")
    sim: EvacuationSim = entry["sim"]
    counts = sim.cell_counts() if hasattr(sim, "cell_counts") else {}
    return {
        "run_id":           run_id,
        "layout_id":        entry["layout_id"],
        "population":       entry["population"],
        "adherence":        entry["adherence"],
        "use_ml":           entry["use_ml"],
        "done":             sim.done,
        "steps":            sim.step_num,
        "evacuation_time_s":round(sim.evacuation_time_s, 2),
        "exit_flows":       sim.exit_flows_total,
        "steps_history": [
            {
                "step":        r.step,
                "time_s":      r.time_s,
                "alive":       r.alive_count,
                "exited":      r.exited_count,
                "exit_flows":  r.exit_flows,
            }
            for r in sim.history
        ],
    }


@router.get("/simulation/runs/list")
def list_runs():
    """List all active simulation runs."""
    with _lock:
        return [
            {"run_id": rid, "status": e["status"], "layout_id": e["layout_id"],
             "done": e["sim"].done, "steps": e["sim"].step_num}
            for rid, e in _sims.items()
        ]
