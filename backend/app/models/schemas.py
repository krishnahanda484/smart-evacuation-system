"""
Pydantic v2 schemas — mirroring the OpenAPI components/schemas.
Used for both request validation and response serialisation in FastAPI.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared sub-objects
# ---------------------------------------------------------------------------

class ExitInfo(BaseModel):
    id:    int
    row:   int
    col:   int
    label: str


class CellTypeCounts(BaseModel):
    FREE:     int
    WALL:     int
    OBSTACLE: int
    EXIT:     int


# ---------------------------------------------------------------------------
# Grid data (the raw 2-D array + summary)
# ---------------------------------------------------------------------------

class GridData(BaseModel):
    cells:      List[List[int]]   = Field(description="Row-major 2-D array of cell type integers")
    width:      int               = Field(description="Number of columns")
    height:     int               = Field(description="Number of rows")
    cell_types: CellTypeCounts    = Field(description="Count of each cell type")
    exits:      List[ExitInfo]    = Field(description="Named exit locations")


# ---------------------------------------------------------------------------
# Layout metadata (no grid data — used in list responses)
# ---------------------------------------------------------------------------

class LayoutMeta(BaseModel):
    id:               str
    name:             str
    description:      str
    width:            int
    height:           int
    resolution_cm:    float
    exit_count:       int
    wall_count:       int
    obstacle_count:   int
    free_count:       int
    physical_width_m: float
    physical_height_m: float
    passable_area_m2:  float
    is_sample:        bool


# ---------------------------------------------------------------------------
# Full layout (metadata + grid)
# ---------------------------------------------------------------------------

class Layout(BaseModel):
    meta: LayoutMeta
    grid: GridData


# ---------------------------------------------------------------------------
# Request body schemas
# ---------------------------------------------------------------------------

class ExitInput(BaseModel):
    row:   int
    col:   int
    label: Optional[str] = None


class RectInput(BaseModel):
    r1: int
    c1: int
    r2: int
    c2: int


class LayoutInput(BaseModel):
    """
    Schema for creating a custom layout.

    Supports two modes:
      1. Supply `cells` directly (full 2-D grid).
      2. Supply `walls`, `obstacles`, `exits` to build from primitives.
    The two modes can be combined: `cells` is applied first, then the other
    fields are overlaid on top.
    """
    name:          str
    description:   str             = ""
    width:         int             = Field(ge=5, le=500)
    height:        int             = Field(ge=5, le=500)
    resolution_cm: float           = Field(default=30.0, ge=1.0, le=200.0)
    cells:         Optional[List[List[int]]] = None
    walls:         List[RectInput] = Field(default_factory=list)
    obstacles:     List[RectInput] = Field(default_factory=list)
    exits:         List[ExitInput] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthStatus(BaseModel):
    status: str
