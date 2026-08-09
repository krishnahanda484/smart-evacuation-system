"""Module 8 — Evaluation suite API routes."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..modules.evaluation import run_evaluation, get_eval_status

router = APIRouter(prefix="/api", tags=["evaluation"])


class EvalInput(BaseModel):
    layout_id:     str   = "sample_medium"
    population:    int   = Field(default=300,  ge=20, le=5000)
    adherence_rate:float = Field(default=0.70, ge=0.0, le=1.0)
    n_runs:        int   = Field(default=20,   ge=5,  le=100)


@router.post("/evaluation/run", status_code=202)
def trigger_evaluation(body: EvalInput, background_tasks: BackgroundTasks):
    """Run A/B evaluation: greedy baseline vs ML-guided (background)."""
    s = get_eval_status()
    if s["state"] == "running":
        raise HTTPException(status_code=409, detail="Evaluation already running.")

    background_tasks.add_task(
        run_evaluation,
        body.layout_id, body.population, body.adherence_rate, body.n_runs,
    )
    return {"message": f"Evaluation started: {body.n_runs} runs each side. Poll /api/evaluation/status."}


@router.get("/evaluation/status")
def evaluation_status():
    """Return evaluation progress and results."""
    return get_eval_status()


@router.get("/evaluation/results")
def evaluation_results():
    """Return the completed evaluation results."""
    s = get_eval_status()
    if s["state"] != "done":
        raise HTTPException(status_code=404, detail="No completed evaluation. Run /api/evaluation/run first.")
    return s["result"]
