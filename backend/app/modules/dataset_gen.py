"""
Module 3 — Synthetic Dataset Generator
========================================
Runs the simulation engine thousands of times with varied parameters to
produce the ML training dataset.

Design rationale (for methodology section):
  Every row in the CSV comes from an actual simulation run — no random or
  synthetic rows are fabricated.  This ensures the training distribution
  matches the deployment distribution, which is a core requirement for
  reliable real-time prediction (Goodfellow et al., 2016).

  Varied parameters:
    • Layout:        small, medium, large (3 layouts)
    • Population:    5 levels uniformly spaced from ~5% to ~60% of passable
                     area (the paper uses 500–10 000; we scale to grid size)
    • Adherence:     0.30, 0.50, 0.70, 0.90  (4 levels)
    Total design points: 3 × 5 × 4 = 60 combinations.
    Each combination is replicated ≥5 times (different random seeds).
    Target: ≥300 runs → ≥300 000 rows.

  Label construction:
    congestion_in_Xs  — congestion of the same region X simulated seconds
                        later (default 30 s = 60 steps at 0.5 s/step).
                        Rows near the end of each run (where no future
                        step exists) are assigned the final congestion value.
    evacuation_time   — total simulated time (s) for this run.  Identical
                        for all rows from the same run — used by the
                        secondary regressor.

Data dictionary saved alongside the CSV.
"""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .grid_map import GridMap
from .sample_layouts import build_small, build_medium, build_large
from .simulation import EvacuationSim, DT

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR   = Path(__file__).parent.parent.parent / "data"
DATASET_CSV = DATA_DIR / "simulation_dataset.csv"
DICT_JSON   = DATA_DIR / "data_dictionary.json"

DATA_COLUMNS = [
    "run_id", "layout_id", "population_total", "adherence_rate",
    "step", "timestamp_s",
    "region_id", "center_row", "center_col",
    "local_population", "passable_cells", "local_density",
    "nearest_exit_id", "nearest_exit_dist",
    "exit_flow_this_step",
    "avg_walking_speed",
    "current_congestion",
    "congestion_in_30s",      # LABEL 1
    "evacuation_time_s",      # LABEL 2
]

DATA_DICT = {
    "run_id":            "Unique identifier for this simulation run.",
    "layout_id":         "Which floor plan was used (sample_small / medium / large).",
    "population_total":  "Total occupants placed at the start of this run.",
    "adherence_rate":    "Fraction of agents that follow the guided exit recommendation.",
    "step":              "Discrete time-step index (integer).",
    "timestamp_s":       "Simulated elapsed time in seconds (step × 0.5).",
    "region_id":         "Spatial region index (grid partitioned into 8×8-cell blocks).",
    "center_row":        "Row of the region centre cell.",
    "center_col":        "Column of the region centre cell.",
    "local_population":  "Number of agents currently in this region.",
    "passable_cells":    "Number of FREE/EXIT cells in this region (constant per layout).",
    "local_density":     "local_population / passable_cells  ∈ [0, MAX_DENSITY].",
    "nearest_exit_id":   "Index of the nearest exit to this region's centre (BFS).",
    "nearest_exit_dist": "BFS distance (cells) from region centre to nearest exit.",
    "exit_flow_this_step":"Number of agents that exited via any exit during this step.",
    "avg_walking_speed":  "Mean speed (cells/step) of agents inside this region.",
    "current_congestion": "Density-normalised congestion ∈ [0, 1].",
    "congestion_in_30s":  "LABEL — current_congestion of this region 30 s later (60 steps).",
    "evacuation_time_s":  "LABEL — total simulated evacuation time for this run (s).",
}

# ---------------------------------------------------------------------------
# Generation status (shared state for the background task)
# ---------------------------------------------------------------------------

_status: Dict[str, Any] = {
    "state":        "idle",      # idle | running | done | error
    "runs_done":    0,
    "runs_total":   0,
    "rows_written": 0,
    "started_at":   None,
    "finished_at":  None,
    "error":        None,
    "sample_rows":  [],
}


def _safe_float(v: Any) -> Any:
    """Convert a value to a JSON-safe float (replace nan/inf with 0)."""
    if isinstance(v, float):
        import math
        if math.isnan(v) or math.isinf(v):
            return 0.0
    return v


def get_status() -> Dict[str, Any]:
    s = dict(_status)
    # Sanitize sample_rows so NaN/inf don't break JSON serialization
    s["sample_rows"] = [
        {k: _safe_float(val) for k, val in row.items()}
        for row in s["sample_rows"]
    ]
    return s


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def _layout_configs() -> List[Dict]:
    """Return list of (layout_id, gm, passable_cells)."""
    configs = []
    for lid, builder in [
        ("sample_small",  build_small),
        ("sample_medium", build_medium),
        ("sample_large",  build_large),
    ]:
        gm = builder()
        counts = gm.cell_counts()
        passable = counts["FREE"] + counts["EXIT"]
        configs.append({"layout_id": lid, "gm": gm, "passable": passable})
    return configs


def _pop_levels(passable: int, n_levels: int = 5) -> List[int]:
    """
    Return n_levels population sizes from 5% to 60% of passable area.
    Capped at 5000 to keep simulation tractable.
    """
    lo = max(20, int(passable * 0.05))
    hi = min(5000, int(passable * 0.60))
    return [max(20, int(lo + (hi - lo) * i / (n_levels - 1))) for i in range(n_levels)]


ADHERENCE_LEVELS = [0.30, 0.50, 0.70, 0.90]
REPS_PER_CONFIG  = 5    # replication count per (layout, pop, adherence)
PRED_HORIZON     = 60   # steps ahead for congestion label (= 30 s at 0.5 s/step)
MAX_SIM_STEPS    = 1200


def generate_dataset(
    progress_cb: Optional[Callable[[int, int], None]] = None
) -> None:
    """
    Generate the full training dataset and write it to DATASET_CSV.
    This function blocks until complete — run in a thread.
    """
    global _status
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    layout_cfgs = _layout_configs()
    all_configs = [
        (lcfg, pop, adh, rep)
        for lcfg in layout_cfgs
        for pop in _pop_levels(lcfg["passable"])
        for adh in ADHERENCE_LEVELS
        for rep in range(REPS_PER_CONFIG)
    ]
    total_runs = len(all_configs)

    _status.update({
        "state":        "running",
        "runs_done":    0,
        "runs_total":   total_runs,
        "rows_written": 0,
        "started_at":   time.time(),
        "finished_at":  None,
        "error":        None,
        "sample_rows":  [],
    })

    run_id = 0
    rows_written = 0

    with open(DATASET_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=DATA_COLUMNS)
        writer.writeheader()

        for (lcfg, pop, adh, rep) in all_configs:
            try:
                sim = EvacuationSim(
                    gm=lcfg["gm"],
                    population=pop,
                    adherence_rate=adh,
                    seed=run_id * 7 + rep,
                )
                sim.run_to_completion(max_steps=MAX_SIM_STEPS)
                evac_time = sim.evacuation_time_s

                # Build rows from history
                hist = sim.history
                n_steps = len(hist)
                
                # Compute total exit flow per step for the "exit_flow_this_step" feature
                step_total_flow = [sum(h.exit_flows.values()) for h in hist]

                for si, rec in enumerate(hist):
                    future_si = min(si + PRED_HORIZON, n_steps - 1)
                    future_congest = {
                        rs["region_id"]: rs["current_congestion"]
                        for rs in hist[future_si].region_stats
                    }
                    for rs in rec.region_stats:
                        row = {
                            "run_id":            run_id,
                            "layout_id":         lcfg["layout_id"],
                            "population_total":  pop,
                            "adherence_rate":    adh,
                            "step":              rec.step,
                            "timestamp_s":       round(rec.time_s, 2),
                            "region_id":         rs["region_id"],
                            "center_row":        rs["center_row"],
                            "center_col":        rs["center_col"],
                            "local_population":  rs["local_population"],
                            "passable_cells":    rs["passable_cells"],
                            "local_density":     _safe_float(rs["local_density"]),
                            "nearest_exit_id":   rs["nearest_exit_id"],
                            "nearest_exit_dist": round(_safe_float(rs["nearest_exit_dist"]), 2),
                            "exit_flow_this_step": step_total_flow[si],
                            "avg_walking_speed": _safe_float(rs["avg_walking_speed"]),
                            "current_congestion":_safe_float(rs["current_congestion"]),
                            "congestion_in_30s": _safe_float(future_congest.get(rs["region_id"], rs["current_congestion"])),
                            "evacuation_time_s": round(_safe_float(evac_time), 2),
                        }
                        writer.writerow(row)
                        rows_written += 1

                        if rows_written <= 5:
                            _status["sample_rows"].append(row)

                fh.flush()
                run_id += 1
                _status["runs_done"]    = run_id
                _status["rows_written"] = rows_written
                if progress_cb:
                    progress_cb(run_id, total_runs)

            except Exception as e:
                run_id += 1
                continue

    # Write data dictionary
    with open(DICT_JSON, "w") as f:
        json.dump(DATA_DICT, f, indent=2)

    _status.update({
        "state":        "done",
        "rows_written": rows_written,
        "finished_at":  time.time(),
    })


def dataset_exists() -> bool:
    return DATASET_CSV.exists() and DATASET_CSV.stat().st_size > 0
