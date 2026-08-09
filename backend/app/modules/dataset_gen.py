"""
Module 3 — Synthetic Dataset Generator
========================================
Runs the simulation engine across varied parameters to produce the ML
training dataset.  Each row is derived from an actual simulation run —
no fabricated data.

inf-guard policy:
  Rows where nearest_exit_dist is inf (region completely walled-off from
  all exits in BFS) are SKIPPED.  Such cells are physically unreachable
  and would produce nonsensical features.  All division-based features
  (local_density = local_population / passable_cells) are guarded with
  max(1, denominator) to prevent division-by-zero, with the result clipped
  to [0, MAX_DENSITY_RATIO].  This produces a clean, bounded dataset.
"""

from __future__ import annotations

import csv
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .grid_map import GridMap
from .sample_layouts import build_small, build_medium, build_large
from .simulation import EvacuationSim, DT, MAX_DENSITY

DATA_DIR    = Path(__file__).parent.parent.parent / "data"
DATASET_CSV = DATA_DIR / "simulation_dataset.csv"
DICT_JSON   = DATA_DIR / "data_dictionary.json"

MAX_DENSITY_RATIO = MAX_DENSITY  # upper bound for local_density clipping

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
    "layout_id":         "Floor plan used (sample_small / medium / large).",
    "population_total":  "Total occupants placed at the start.",
    "adherence_rate":    "Fraction of agents following guided exit recommendation.",
    "step":              "Discrete time-step index (integer).",
    "timestamp_s":       "Simulated elapsed time in seconds (step × 0.5).",
    "region_id":         "Spatial region index (8×8-cell blocks).",
    "center_row":        "Row of the region centre cell.",
    "center_col":        "Column of the region centre cell.",
    "local_population":  "Number of agents currently in this region.",
    "passable_cells":    "Number of FREE/EXIT cells in this region (constant per layout).",
    "local_density":     "local_population / passable_cells ∈ [0, MAX_DENSITY_RATIO].",
    "nearest_exit_id":   "Index of the nearest exit to this region's centre (BFS).",
    "nearest_exit_dist": "BFS distance (cells) from region centre to nearest exit (finite only).",
    "exit_flow_this_step":"Agents that exited via any exit during this step.",
    "avg_walking_speed": "Mean speed (cells/step) of agents inside this region.",
    "current_congestion":"Density-normalised congestion ∈ [0, 1].",
    "congestion_in_30s": "LABEL — current_congestion of this region 30 s later (60 steps).",
    "evacuation_time_s": "LABEL — total simulated evacuation time for this run (s).",
}

_status: Dict[str, Any] = {
    "state":        "idle",
    "runs_done":    0,
    "runs_total":   0,
    "rows_written": 0,
    "started_at":   None,
    "finished_at":  None,
    "error":        None,
    "sample_rows":  [],
}


def get_status() -> Dict[str, Any]:
    return dict(_status)


def _layout_configs() -> List[Dict]:
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
    lo = max(20, int(passable * 0.05))
    hi = min(5000, int(passable * 0.60))
    return [max(20, int(lo + (hi - lo) * i / (n_levels - 1))) for i in range(n_levels)]


ADHERENCE_LEVELS = [0.30, 0.50, 0.70, 0.90]
REPS_PER_CONFIG  = 5
PRED_HORIZON     = 60   # steps ahead (= 30 s at 0.5 s/step)
MAX_SIM_STEPS    = 1200


def generate_dataset(progress_cb: Optional[Callable[[int, int], None]] = None) -> None:
    """Generate the full training dataset. Blocks — run in a thread."""
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
    rows_skipped = 0

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

                hist = sim.history
                n_steps = len(hist)
                step_total_flow = [sum(h.exit_flows.values()) for h in hist]

                for si, rec in enumerate(hist):
                    future_si = min(si + PRED_HORIZON, n_steps - 1)
                    future_congest = {
                        rs["region_id"]: rs["current_congestion"]
                        for rs in hist[future_si].region_stats
                    }
                    for rs in rec.region_stats:
                        # ── inf-guard: skip unreachable regions ──────
                        nearest_dist = rs["nearest_exit_dist"]
                        if not math.isfinite(nearest_dist):
                            rows_skipped += 1
                            continue

                        # ── guard local_density against div-by-zero ──
                        passable = max(1, rs["passable_cells"])
                        local_density = min(
                            float(rs["local_population"]) / passable,
                            MAX_DENSITY_RATIO,
                        )

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
                            "passable_cells":    passable,
                            "local_density":     round(local_density, 4),
                            "nearest_exit_id":   rs["nearest_exit_id"],
                            "nearest_exit_dist": round(nearest_dist, 2),
                            "exit_flow_this_step": step_total_flow[si],
                            "avg_walking_speed": rs["avg_walking_speed"],
                            "current_congestion":rs["current_congestion"],
                            "congestion_in_30s": future_congest.get(
                                rs["region_id"], rs["current_congestion"]
                            ),
                            "evacuation_time_s": round(evac_time, 2),
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

            except Exception:
                run_id += 1
                continue

    print(f"[Dataset] Done: {rows_written:,} rows written, {rows_skipped} inf-rows skipped.")
    with open(DICT_JSON, "w") as f:
        json.dump(DATA_DICT, f, indent=2)

    _status.update({
        "state":        "done",
        "rows_written": rows_written,
        "finished_at":  time.time(),
    })


def dataset_exists() -> bool:
    return DATASET_CSV.exists() and DATASET_CSV.stat().st_size > 0
