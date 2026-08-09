"""
Module 1 — Built-in Sample Layouts
====================================
Three floor plans are provided so the system can be tested without uploading
any files.  Each is constructed using the GridMap drawing primitives, so the
code also serves as a worked example of the JSON schema format.

Layout design rationale (for methodology section):
  • Small  (20 cols × 30 rows = 6 m × 9 m):
      Models a single classroom.  Narrow width creates a natural bottleneck
      that amplifies congestion effects — useful for tuning the ML model on
      small-scale scenarios.

  • Medium (40 cols × 60 rows = 12 m × 18 m):
      Models one floor of an open-plan office with a central corridor and
      cubicle clusters.  Four exits reflect real fire-code requirements for
      medium occupancy spaces (BS 9999 / IBC).

  • Large  (60 cols × 100 rows = 18 m × 30 m):
      Models a mall wing with two parallel shopping corridors and anchor-store
      obstacles.  Six distributed exits test the optimizer's ability to balance
      load across spatially diverse options.

Resolution: 30 cm per cell throughout (matching the reference paper).
"""

from __future__ import annotations
from typing import Dict, Any
from .grid_map import GridMap, CellType


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _meta(layout_id: str, name: str, description: str,
          gm: GridMap) -> Dict[str, Any]:
    counts = gm.cell_counts()
    return {
        "id":            layout_id,
        "name":          name,
        "description":   description,
        "width":         gm.width,
        "height":        gm.height,
        "resolution_cm": gm.resolution_cm,
        "exit_count":    len(gm.exits),
        "wall_count":    counts.get("WALL", 0),
        "obstacle_count":counts.get("OBSTACLE", 0),
        "free_count":    counts.get("FREE", 0),
        "physical_width_m":  gm.physical_width_m,
        "physical_height_m": gm.physical_height_m,
        "passable_area_m2":  gm.passable_area_m2,
        "is_sample":     True,
    }


# ---------------------------------------------------------------------------
# Layout A — Small Classroom (20 × 30)
# ---------------------------------------------------------------------------

def build_small() -> GridMap:
    """
    6 m × 9 m classroom.
    • Thick outer walls (2 cells)
    • Teacher's desk block at the north end (row 2–4, col 8–11)
    • Four rows of student desks (2×1 each, arranged in a 3-column grid)
    • 2 exits: south-centre (main door) + east-centre (fire door)
    """
    W, H = 20, 30
    gm = GridMap(width=W, height=H, resolution_cm=30.0,
                 name="Small Classroom",
                 description="Single classroom, 6 m × 9 m, 2 exits")

    # Outer walls (2-cell thick on all sides)
    gm.fill_rect(0, 0, H - 1, W - 1, CellType.WALL)
    gm.fill_rect(2, 2, H - 3, W - 3, CellType.FREE)

    # Teacher's desk (north end, centred)
    gm.fill_rect(3, 7, 5, 12, CellType.OBSTACLE)

    # Student desks — 3 columns × 4 rows of 2×2 blocks, starting at row 8
    for desk_row in range(4):
        for desk_col in range(3):
            r0 = 8  + desk_row * 5
            c0 = 4  + desk_col * 5
            gm.fill_rect(r0, c0, r0 + 1, c0 + 2, CellType.OBSTACLE)

    # Exit 1: main door — south wall centre
    gm.set_safe(H - 2, W // 2 - 1, CellType.FREE)  # widen doorway
    gm.set_safe(H - 2, W // 2,     CellType.FREE)
    gm.add_exit(H - 1, W // 2, "Main Door (South)")

    # Exit 2: fire door — east wall centre
    mid_r = H // 2
    gm.set_safe(mid_r, W - 2, CellType.FREE)
    gm.add_exit(mid_r, W - 1, "Fire Door (East)")

    return gm


SMALL_ID = "sample_small"
SMALL_NAME = "Small Classroom"
SMALL_DESC = "Single classroom, 6 m × 9 m, 2 exits. Good for baseline single-room evacuation tests."


# ---------------------------------------------------------------------------
# Layout B — Medium Office Floor (40 × 60)
# ---------------------------------------------------------------------------

def build_medium() -> GridMap:
    """
    12 m × 18 m open-plan office.
    • Single-cell outer walls
    • Horizontal service corridor running east–west at mid-height (rows 28–31)
    • Cubicle clusters in the north and south halves
    • 4 exits: one on each wall
    """
    W, H = 40, 60
    gm = GridMap(width=W, height=H, resolution_cm=30.0,
                 name="Medium Office Floor",
                 description="Open-plan office, 12 m × 18 m, 4 exits")

    # Outer walls
    gm.fill_rect(0, 0, H - 1, W - 1, CellType.WALL)
    gm.fill_rect(1, 1, H - 2, W - 2, CellType.FREE)

    # Central horizontal corridor (rows 27–32) — already FREE, mark corridor
    # (left as FREE so agents can walk through; no special encoding needed)

    # North office block — cubicle grid (rows 2–25)
    #   Each cubicle: 2-wide × 3-tall obstacle with 1-cell aisle between
    for row_block in range(4):
        for col_block in range(6):
            r0 = 3  + row_block * 6
            c0 = 2  + col_block * 6
            gm.fill_rect(r0, c0, r0 + 2, c0 + 3, CellType.OBSTACLE)

    # South office block — cubicle grid (rows 34–57)
    for row_block in range(4):
        for col_block in range(6):
            r0 = 34 + row_block * 6
            c0 = 2  + col_block * 6
            gm.fill_rect(r0, c0, r0 + 2, c0 + 3, CellType.OBSTACLE)

    # Server room / meeting room — NE corner (rows 2–10, cols 30–38)
    gm.fill_rect(2, 30, 10, 38, CellType.OBSTACLE)

    # Exit 1: north wall centre
    gm.set_safe(0, W // 2 - 1, CellType.FREE)
    gm.add_exit(0, W // 2, "North Exit")

    # Exit 2: south wall centre
    gm.set_safe(H - 1, W // 2 + 1, CellType.FREE)
    gm.add_exit(H - 1, W // 2, "South Exit")

    # Exit 3: west wall mid-height
    mid_r = H // 2
    gm.set_safe(mid_r - 1, 0, CellType.FREE)
    gm.add_exit(mid_r, 0, "West Exit")

    # Exit 4: east wall mid-height
    gm.set_safe(mid_r + 1, W - 1, CellType.FREE)
    gm.add_exit(mid_r, W - 1, "East Exit")

    return gm


MEDIUM_ID = "sample_medium"
MEDIUM_NAME = "Medium Office Floor"
MEDIUM_DESC = "Open-plan office, 12 m × 18 m, 4 exits. Models typical multi-exit office evacuation."


# ---------------------------------------------------------------------------
# Layout C — Large Mall Wing (60 × 100)
# ---------------------------------------------------------------------------

def build_large() -> GridMap:
    """
    18 m × 30 m mall wing.
    • Two parallel shopping corridors (north and south, 4 cells wide each)
    • Large anchor-store obstacles flanking a central concourse
    • 6 exits: 2 at each end + 2 on the long sides
    """
    W, H = 60, 100
    gm = GridMap(width=W, height=H, resolution_cm=30.0,
                 name="Large Mall Wing",
                 description="Shopping mall wing, 18 m × 30 m, 6 exits")

    # Outer walls
    gm.fill_rect(0, 0, H - 1, W - 1, CellType.WALL)
    gm.fill_rect(1, 1, H - 2, W - 2, CellType.FREE)

    # ── North corridor row 5–10 is already free ──
    # ── South corridor row 89–94 is already free ──

    # Anchor stores — large rectangular obstacles
    # NW anchor (rows 2–40, cols 2–18)
    gm.fill_rect(2, 2, 40, 18, CellType.OBSTACLE)
    # NE anchor (rows 2–40, cols 41–57)
    gm.fill_rect(2, 41, 40, 57, CellType.OBSTACLE)
    # SW anchor (rows 60–97, cols 2–18)
    gm.fill_rect(60, 2, 97, 18, CellType.OBSTACLE)
    # SE anchor (rows 60–97, cols 41–57)
    gm.fill_rect(60, 41, 97, 57, CellType.OBSTACLE)

    # Small kiosks in the central concourse
    for i, (r0, c0) in enumerate([(45, 10), (45, 28), (45, 46),
                                   (53, 10), (53, 28), (53, 46)]):
        gm.fill_rect(r0, c0, r0 + 3, c0 + 3, CellType.OBSTACLE)

    # ── Exits ──
    # Exit 1 & 2: north wall (2 doors)
    gm.add_exit(0, 15, "North Exit A")
    gm.add_exit(0, 44, "North Exit B")

    # Exit 3 & 4: south wall (2 doors)
    gm.add_exit(H - 1, 15, "South Exit A")
    gm.add_exit(H - 1, 44, "South Exit B")

    # Exit 5: west wall (mid-height)
    gm.add_exit(H // 2, 0, "West Exit")

    # Exit 6: east wall (mid-height)
    gm.add_exit(H // 2, W - 1, "East Exit")

    return gm


LARGE_ID = "sample_large"
LARGE_NAME = "Large Mall Wing"
LARGE_DESC = "Shopping mall wing, 18 m × 30 m, 6 exits. Stress-tests multi-exit route optimization."


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SAMPLE_REGISTRY: Dict[str, Any] = {}


def _register():
    for layout_id, builder, name, desc in [
        (SMALL_ID,  build_small,  SMALL_NAME,  SMALL_DESC),
        (MEDIUM_ID, build_medium, MEDIUM_NAME, MEDIUM_DESC),
        (LARGE_ID,  build_large,  LARGE_NAME,  LARGE_DESC),
    ]:
        gm = builder()
        SAMPLE_REGISTRY[layout_id] = {
            "meta":   _meta(layout_id, name, desc, gm),
            "grid":   gm,
        }


_register()


def get_sample(layout_id: str) -> Dict[str, Any] | None:
    return SAMPLE_REGISTRY.get(layout_id)


def list_samples() -> list[Dict[str, Any]]:
    return [v["meta"] for v in SAMPLE_REGISTRY.values()]
