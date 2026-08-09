"""
Module 1 — Layout API routes
"""

from __future__ import annotations

import json
import uuid
from typing import List

from fastapi import APIRouter, HTTPException

from ..database import (
    insert_layout, get_layout_row, list_layout_rows, layout_exists
)
from ..models.schemas import Layout, LayoutInput, LayoutMeta, GridData, ExitInfo, CellTypeCounts
from ..modules.grid_map import GridMap, CellType, build_from_schema
from ..modules.sample_layouts import SAMPLE_REGISTRY, list_samples, get_sample

router = APIRouter(prefix="/api", tags=["layouts"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_meta(row) -> LayoutMeta:
    return LayoutMeta(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        width=row["width"],
        height=row["height"],
        resolution_cm=row["resolution_cm"],
        exit_count=row["exit_count"],
        wall_count=row["wall_count"],
        obstacle_count=row["obstacle_count"],
        free_count=row["free_count"],
        physical_width_m=row["physical_width_m"],
        physical_height_m=row["physical_height_m"],
        passable_area_m2=row["passable_area_m2"],
        is_sample=bool(row["is_sample"]),
    )


def _gm_to_grid_data(gm: GridMap) -> GridData:
    counts = gm.cell_counts()
    return GridData(
        cells=gm.cells,
        width=gm.width,
        height=gm.height,
        cell_types=CellTypeCounts(
            FREE=counts.get("FREE", 0),
            WALL=counts.get("WALL", 0),
            OBSTACLE=counts.get("OBSTACLE", 0),
            EXIT=counts.get("EXIT", 0),
        ),
        exits=[ExitInfo(**e.to_dict()) for e in gm.exits],
    )


def _load_gm(layout_id: str) -> tuple[GridMap, dict]:
    """Load a GridMap and its meta dict from DB or sample registry."""
    # Check sample registry first
    sample = get_sample(layout_id)
    if sample:
        return sample["grid"], sample["meta"]

    row = get_layout_row(layout_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Layout '{layout_id}' not found.")

    raw = json.loads(row["grid_json"])
    gm = GridMap.from_dict(raw, name=row["name"], description=row["description"])
    gm.resolution_cm = row["resolution_cm"]
    meta = dict(row)
    return gm, meta


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/layouts", response_model=List[LayoutMeta])
def list_layouts():
    """List all available layouts (samples + user-created)."""
    metas: List[LayoutMeta] = []

    # Samples always come first
    for s in list_samples():
        metas.append(LayoutMeta(**s))

    # Then user-created layouts from DB (skip sample IDs already listed)
    sample_ids = {s["id"] for s in list_samples()}
    for row in list_layout_rows():
        if row["id"] not in sample_ids:
            metas.append(_row_to_meta(row))

    return metas


@router.get("/layouts/{layout_id}", response_model=Layout)
def get_layout(layout_id: str):
    """Return full layout data (metadata + grid)."""
    gm, meta = _load_gm(layout_id)
    return Layout(
        meta=LayoutMeta(**{k: meta[k] for k in LayoutMeta.model_fields}),
        grid=_gm_to_grid_data(gm),
    )


@router.get("/layouts/{layout_id}/grid", response_model=GridData)
def get_layout_grid(layout_id: str):
    """Return only the raw grid data for a layout."""
    gm, _ = _load_gm(layout_id)
    return _gm_to_grid_data(gm)


@router.post("/layouts", response_model=LayoutMeta, status_code=201)
def create_layout(body: LayoutInput):
    """Create and persist a custom layout from a JSON schema."""
    schema = body.model_dump()

    # Build GridMap
    gm = build_from_schema(schema)

    # Validate
    issues = gm.validate()
    if issues:
        raise HTTPException(status_code=422, detail={"validation_issues": issues})

    layout_id = f"custom_{uuid.uuid4().hex[:8]}"
    counts = gm.cell_counts()
    meta = {
        "id":               layout_id,
        "name":             body.name,
        "description":      body.description,
        "width":            gm.width,
        "height":           gm.height,
        "resolution_cm":    gm.resolution_cm,
        "exit_count":       len(gm.exits),
        "wall_count":       counts.get("WALL", 0),
        "obstacle_count":   counts.get("OBSTACLE", 0),
        "free_count":       counts.get("FREE", 0),
        "physical_width_m": gm.physical_width_m,
        "physical_height_m":gm.physical_height_m,
        "passable_area_m2": gm.passable_area_m2,
        "is_sample":        False,
    }

    grid_json = json.dumps(gm.to_dict())
    insert_layout(layout_id, meta, grid_json)

    return LayoutMeta(**meta)
