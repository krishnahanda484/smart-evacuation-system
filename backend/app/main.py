"""
Smart Evacuation System — FastAPI application entry point
Modules: 1 (layouts), 2 (simulation), 3 (dataset), 4 (ML), 5 (predictor),
         6 (API), 8 (evaluation)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db, insert_layout, layout_exists
from .models.schemas import HealthStatus
from .modules.sample_layouts import SAMPLE_REGISTRY
from .modules.predictor import get_predictor
from .routes.layouts import router as layouts_router
from .routes.simulation import router as sim_router
from .routes.dataset import router as dataset_router
from .routes.ml import router as ml_router
from .routes.evaluation import router as eval_router

import json


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    for layout_id, entry in SAMPLE_REGISTRY.items():
        if not layout_exists(layout_id):
            gm   = entry["grid"]
            meta = entry["meta"]
            grid_json = json.dumps(gm.to_dict())
            insert_layout(layout_id, meta, grid_json)
    # Try to pre-load ML model (non-fatal if not trained yet)
    try:
        get_predictor().load()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Smart Evacuation System API",
    description=(
        "Research prototype: AI-Based Smart Evacuation System with "
        "Predictive Congestion Analysis and Dynamic Route Optimization. "
        "Ibrahim et al., IEEE Access 2023."
    ),
    version="1.0.0",
    lifespan=lifespan,
    root_path=os.getenv("ROOT_PATH", ""),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/healthz", response_model=HealthStatus, tags=["health"])
def health_check():
    return HealthStatus(status="ok")


app.include_router(layouts_router)
app.include_router(sim_router)
app.include_router(dataset_router)
app.include_router(ml_router)
app.include_router(eval_router)
