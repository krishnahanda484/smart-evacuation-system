"""
Module 1 — Building Layout Parser & Grid Map Generator
=======================================================
Design rationale (for methodology section):
  The paper uses a 30 cm/cell discrete grid — coarse enough that a modern
  building fits in memory but fine enough to model single-occupant-width
  corridors (~90 cm → 3 cells).  Each cell carries exactly one of four
  semantic values so that the simulation engine (Module 2) can apply simple
  integer comparisons in its inner loop rather than expensive geometry queries.

Cell encoding
  FREE     = 0  — passable floor space
  WALL     = 1  — structural wall (impassable)
  OBSTACLE = 2  — furniture / equipment (impassable)
  EXIT     = 3  — emergency exit (passable; terminates an agent's path)

Coordinate convention: (row, col), origin top-left, row increases downward.
This matches raster image coordinates and simplifies numpy indexing later.
"""

from __future__ import annotations

from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any


# ---------------------------------------------------------------------------
# Cell type constants
# ---------------------------------------------------------------------------

class CellType(IntEnum):
    FREE     = 0
    WALL     = 1
    OBSTACLE = 2
    EXIT     = 3

    @property
    def label(self) -> str:
        return self.name.capitalize()

    @property
    def color_hex(self) -> str:
        """Reference colour used by the dashboard heatmap layer."""
        return {
            CellType.FREE:     "#F5F5F5",
            CellType.WALL:     "#2D3748",
            CellType.OBSTACLE: "#805AD5",
            CellType.EXIT:     "#38A169",
        }[self]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExitPoint:
    id:    int
    row:   int
    col:   int
    label: str = ""

    def __post_init__(self):
        if not self.label:
            self.label = f"Exit {self.id + 1}"

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "row": self.row, "col": self.col, "label": self.label}


@dataclass
class GridMap:
    """
    2-D cellular grid representing a building floor plan.

    Storage: list-of-lists (row-major).  Row 0 is the north edge, col 0 the
    west edge.  Designed so it can be trivially converted to a numpy array for
    the simulation engine without changing the public interface.
    """
    width:          int            # number of columns
    height:         int            # number of rows
    resolution_cm:  float = 30.0  # physical size of one cell in centimetres
    cells:          List[List[int]] = field(default_factory=list)
    exits:          List[ExitPoint] = field(default_factory=list)
    name:           str = ""
    description:    str = ""

    def __post_init__(self):
        if not self.cells:
            self.cells = [[CellType.FREE] * self.width for _ in range(self.height)]

    # ------------------------------------------------------------------
    # Bounds & access
    # ------------------------------------------------------------------

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def get(self, row: int, col: int) -> int:
        if not self.in_bounds(row, col):
            raise IndexError(f"({row},{col}) out of bounds {self.height}×{self.width}")
        return self.cells[row][col]

    def set(self, row: int, col: int, cell_type: int) -> None:
        if not self.in_bounds(row, col):
            raise IndexError(f"({row},{col}) out of bounds {self.height}×{self.width}")
        self.cells[row][col] = int(cell_type)

    def set_safe(self, row: int, col: int, cell_type: int) -> None:
        """Like set() but silently ignores out-of-bounds coordinates."""
        if self.in_bounds(row, col):
            self.cells[row][col] = int(cell_type)

    def is_passable(self, row: int, col: int) -> bool:
        """True if an agent can stand in this cell (FREE or EXIT)."""
        if not self.in_bounds(row, col):
            return False
        return self.cells[row][col] in (CellType.FREE, CellType.EXIT)

    # ------------------------------------------------------------------
    # Drawing helpers (used by the sample-layout generator)
    # ------------------------------------------------------------------

    def fill_rect(self, r1: int, c1: int, r2: int, c2: int,
                  cell_type: int) -> None:
        """Fill an axis-aligned rectangle (inclusive on all sides)."""
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                self.set_safe(r, c, cell_type)

    def draw_border(self, r1: int, c1: int, r2: int, c2: int,
                    cell_type: int) -> None:
        """Draw only the perimeter of a rectangle."""
        for c in range(c1, c2 + 1):
            self.set_safe(r1, c, cell_type)
            self.set_safe(r2, c, cell_type)
        for r in range(r1 + 1, r2):
            self.set_safe(r, c1, cell_type)
            self.set_safe(r, c2, cell_type)

    def add_exit(self, row: int, col: int,
                 label: Optional[str] = None) -> ExitPoint:
        """Register an exit cell, overwriting whatever was there before."""
        ep = ExitPoint(id=len(self.exits), row=row, col=col,
                       label=label or f"Exit {len(self.exits) + 1}")
        self.exits.append(ep)
        self.set_safe(row, col, CellType.EXIT)
        return ep

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def cell_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {ct.name: 0 for ct in CellType}
        for row in self.cells:
            for v in row:
                try:
                    counts[CellType(v).name] += 1
                except ValueError:
                    pass
        return counts

    @property
    def total_cells(self) -> int:
        return self.width * self.height

    @property
    def physical_width_m(self) -> float:
        return round(self.width * self.resolution_cm / 100.0, 2)

    @property
    def physical_height_m(self) -> float:
        return round(self.height * self.resolution_cm / 100.0, 2)

    @property
    def passable_area_m2(self) -> float:
        counts = self.cell_counts()
        passable = counts.get("FREE", 0) + counts.get("EXIT", 0)
        cell_m2 = (self.resolution_cm / 100.0) ** 2
        return round(passable * cell_m2, 2)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        """
        Return a list of problem descriptions.  An empty list means the layout
        is usable by the simulation engine.
        """
        issues: List[str] = []
        if not self.exits:
            issues.append("Layout has no exit cells — evacuation impossible.")
        counts = self.cell_counts()
        if counts.get("FREE", 0) + counts.get("EXIT", 0) == 0:
            issues.append("Layout has no passable cells.")
        for ex in self.exits:
            if not self.in_bounds(ex.row, ex.col):
                issues.append(f"{ex.label} is out of bounds.")
            elif self.cells[ex.row][ex.col] != CellType.EXIT:
                issues.append(f"{ex.label} cell is not marked EXIT in the grid.")
        return issues

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        counts = self.cell_counts()
        return {
            "cells":      [list(row) for row in self.cells],
            "width":      self.width,
            "height":     self.height,
            "cell_types": counts,
            "exits":      [e.to_dict() for e in self.exits],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any],
                  name: str = "", description: str = "") -> "GridMap":
        cells  = [list(row) for row in data["cells"]]
        height = len(cells)
        width  = len(cells[0]) if height else 0
        gm = cls(
            width=width, height=height,
            resolution_cm=float(data.get("resolution_cm", 30.0)),
            cells=cells,
            name=name,
            description=description,
        )
        for ex in data.get("exits", []):
            gm.exits.append(ExitPoint(
                id=int(ex["id"]),
                row=int(ex["row"]),
                col=int(ex["col"]),
                label=ex.get("label", f"Exit {ex['id']+1}"),
            ))
        return gm


# ---------------------------------------------------------------------------
# Layout construction from a JSON schema
# ---------------------------------------------------------------------------

def build_from_schema(schema: Dict[str, Any]) -> GridMap:
    """
    Construct a GridMap from a user-supplied JSON schema.

    Schema shape:
      {
        "name":          str,
        "description":   str,          # optional
        "width":         int,           # grid columns
        "height":        int,           # grid rows
        "resolution_cm": float,         # optional, default 30
        "cells":         [[int, ...]],  # optional; if omitted, starts blank
        "walls":   [{"r1":int,"c1":int,"r2":int,"c2":int}, ...],  # optional
        "obstacles":[{"r1":int,"c1":int,"r2":int,"c2":int}, ...], # optional
        "exits":   [{"row":int,"col":int,"label":str}, ...]
      }

    If "cells" is provided it takes priority; walls/obstacles/exits are
    applied on top of it.  This allows importing pre-drawn grids while still
    overriding specific cells.

    Design note: separating exit registration from raw cell values lets the
    simulation engine query named exits (e.g. "Exit A" capacity) without
    scanning the entire grid.
    """
    w   = int(schema["width"])
    h   = int(schema["height"])
    res = float(schema.get("resolution_cm", 30.0))
    gm  = GridMap(width=w, height=h, resolution_cm=res,
                  name=schema.get("name", ""),
                  description=schema.get("description", ""))

    if "cells" in schema:
        for r, row in enumerate(schema["cells"][:h]):
            for c, v in enumerate(row[:w]):
                gm.set_safe(r, c, int(v))

    for rect in schema.get("walls", []):
        gm.fill_rect(rect["r1"], rect["c1"], rect["r2"], rect["c2"],
                     CellType.WALL)

    for rect in schema.get("obstacles", []):
        gm.fill_rect(rect["r1"], rect["c1"], rect["r2"], rect["c2"],
                     CellType.OBSTACLE)

    for ex in schema.get("exits", []):
        gm.add_exit(int(ex["row"]), int(ex["col"]),
                    label=ex.get("label"))

    return gm
