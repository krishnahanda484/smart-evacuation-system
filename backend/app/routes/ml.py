"""Module 6 — ML training & inference API routes."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..modules.ml_train import (
    train_models, get_train_status, models_exist,
    load_metrics, load_writeup
)
from ..modules.predictor import get_predictor
from ..modules.dataset_gen import dataset_exists

router = APIRouter(prefix="/api", tags=["ml"])


@router.get("/ml/status")
def ml_status():
    """Return training status and last known metrics."""
    return {
        **get_train_status(),
        "models_exist":   models_exist(),
        "dataset_exists": dataset_exists(),
        "predictor_loaded": get_predictor().is_loaded,
        "predictor_model":  get_predictor().model_name,
    }


@router.post("/ml/train", status_code=202)
def trigger_training(background_tasks: BackgroundTasks):
    """Start ML training as a background task."""
    s = get_train_status()
    if s["state"] == "running":
        raise HTTPException(status_code=409, detail="Training already running.")
    if not dataset_exists():
        raise HTTPException(status_code=400, detail="Dataset not found. Generate it first via /api/dataset/generate.")

    background_tasks.add_task(train_models)
    return {"message": "Training started. Poll /api/ml/status for progress."}


@router.get("/ml/metrics")
def get_metrics():
    """Return model comparison table and evaluation metrics."""
    metrics = load_metrics()
    if not metrics:
        raise HTTPException(status_code=404, detail="No metrics found. Train models first.")
    return metrics


@router.get("/ml/writeup")
def get_writeup():
    """Return the auto-generated model comparison write-up for the paper."""
    writeup = load_writeup()
    if not writeup:
        raise HTTPException(status_code=404, detail="No writeup found. Train models first.")
    return writeup


@router.post("/ml/reload")
def reload_predictor():
    """Reload the predictor from disk (after new training run)."""
    p = get_predictor()
    ok = p.load()
    return {"loaded": ok, "model_name": p.model_name}
