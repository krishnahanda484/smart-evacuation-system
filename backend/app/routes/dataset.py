"""Module 6 — Dataset generation API routes."""
from __future__ import annotations

import threading

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..modules.dataset_gen import (
    generate_dataset, get_status, dataset_exists,
    DATASET_CSV, DICT_JSON
)

router = APIRouter(prefix="/api", tags=["dataset"])


def _sanitize(obj):
    """Recursively replace float inf/nan with None for JSON safety."""
    import math
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(i) for i in obj]
    return obj


@router.get("/dataset/status")
def dataset_status():
    """Return generation progress and sample rows."""
    return _sanitize(get_status())


@router.post("/dataset/generate", status_code=202)
def trigger_generate(background_tasks: BackgroundTasks):
    """Start dataset generation as a background task."""
    s = get_status()
    if s["state"] == "running":
        raise HTTPException(status_code=409, detail="Generation already running.")

    background_tasks.add_task(generate_dataset)
    return {"message": "Dataset generation started. Poll /api/dataset/status for progress."}


@router.get("/dataset/download")
def download_csv():
    """Download the generated dataset CSV."""
    if not dataset_exists():
        raise HTTPException(status_code=404, detail="Dataset not yet generated.")
    return FileResponse(
        path=str(DATASET_CSV),
        media_type="text/csv",
        filename="simulation_dataset.csv",
    )


@router.get("/dataset/dictionary")
def data_dictionary():
    """Return the data dictionary (column descriptions)."""
    if not DICT_JSON.exists():
        raise HTTPException(status_code=404, detail="Data dictionary not available yet.")
    import json
    with open(DICT_JSON) as f:
        return json.load(f)
