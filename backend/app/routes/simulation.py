"""Module 6 — Simulation API routes."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..modules.grid_map import GridMap
from ..modules.simulation import EvacuationSim, DT
from ..modules.predictor import RouteOptimizer, get_predictor
from ..modules.sample_layouts import get_sample
from ..database import get_layout_row
import json

router = APIRouter(prefix="/api", tags=["simulation"])

_sims: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


class SimStartInput(BaseModel):
    layout_id:      str
    population:     int   = Field(ge=1, le=10000)
    adherence_rate: float = Field(default=0.70, ge=0.0, le=1.0)
    use_ml:         bool  = Field(default=True)
    seed:           Optional[int] = None


class SimStepInput(BaseModel):
    steps: int = Field(default=1, ge=1, le=200)


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


def _run_optimizer(entry: Dict[str, Any]) -> None:
    """Call recommend_with_zones on the optimizer and cache result in entry."""
    optimizer: Optional[RouteOptimizer] = entry.get("optimizer")
    sim: EvacuationSim = entry["sim"]
    if optimizer and optimizer.should_update():
        recommended, zone_dirs, reroute_evts = optimizer.recommend_with_zones()
        sim.update_guided_targets(recommended)
        # Keep only the 10 most recent rerouting messages (deduplicated)
        existing: List[str] = entry.get("reroute_events", [])
        combined = list(dict.fromkeys(reroute_evts + existing))[:10]
        entry["zone_directions"] = zone_dirs
        entry["reroute_events"]  = combined


def _state_with_guidance(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Return sim state dict enriched with zone directions and reroute events."""
    state = entry["sim"].to_state_dict()
    state["zone_directions"] = entry.get("zone_directions", [])
    state["reroute_events"]  = entry.get("reroute_events", [])
    return state


@router.post("/simulation/start", status_code=201)
def start_simulation(body: SimStartInput):
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
            "sim":             sim,
            "optimizer":       optimizer,
            "use_ml":          body.use_ml,
            "status":          "ready",
            "layout_id":       body.layout_id,
            "population":      body.population,
            "adherence":       body.adherence_rate,
            "zone_directions": [],
            "reroute_events":  [],
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
    with _lock:
        entry = _sims.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found.")

    sim: EvacuationSim = entry["sim"]
    if sim.done:
        return {"state": _state_with_guidance(entry), "done": True}

    for _ in range(body.steps):
        if sim.done:
            break
        sim.step()
        _run_optimizer(entry)

    entry["status"] = "done" if sim.done else "running"
    return {"state": _state_with_guidance(entry), "done": sim.done}


@router.get("/simulation/{run_id}/state")
def get_simulation_state(run_id: str):
    with _lock:
        entry = _sims.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _state_with_guidance(entry)


@router.post("/simulation/{run_id}/run")
def run_to_completion(run_id: str, background_tasks: BackgroundTasks):
    with _lock:
        entry = _sims.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found.")

    def _bg():
        sim: EvacuationSim = entry["sim"]
        entry["status"] = "running"
        while not sim.done and sim.step_num < 2000:
            sim.step()
            _run_optimizer(entry)
        entry["status"] = "done"

    background_tasks.add_task(_bg)
    return {"run_id": run_id, "message": "Running in background. Poll /state for updates."}


@router.post("/simulation/{run_id}/reset")
def reset_simulation(run_id: str):
    with _lock:
        if run_id in _sims:
            del _sims[run_id]
    return {"deleted": run_id}


@router.get("/simulation/{run_id}/results")
def get_simulation_results(run_id: str):
    with _lock:
        entry = _sims.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found.")
    sim: EvacuationSim = entry["sim"]
    return {
        "run_id":            run_id,
        "layout_id":         entry["layout_id"],
        "population":        entry["population"],
        "adherence":         entry["adherence"],
        "use_ml":            entry["use_ml"],
        "done":              sim.done,
        "steps":             sim.step_num,
        "evacuation_time_s": round(sim.evacuation_time_s, 2),
        "exit_flows":        sim.exit_flows_total,
        "steps_history": [
            {
                "step":       r.step,
                "time_s":     r.time_s,
                "alive":      r.alive_count,
                "exited":     r.exited_count,
                "exit_flows": r.exit_flows,
            }
            for r in sim.history
        ],
    }


@router.get("/simulation/runs/list")
def list_runs():
    with _lock:
        return [
            {"run_id": rid, "status": e["status"], "layout_id": e["layout_id"],
             "done": e["sim"].done, "steps": e["sim"].step_num}
            for rid, e in _sims.items()
        ]
