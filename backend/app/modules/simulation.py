"""
Module 2 — Crowd Simulation Engine
====================================
Agent-based, discrete-time simulation of building evacuation.

Design rationale (for methodology section):
  Each occupant is modelled as an autonomous agent with its own position,
  walking speed, target exit, and strategy.  Movement is resolved on the
  same 30 cm cellular grid produced by Module 1.  Agents choose from 8
  cardinal and diagonal directions per Moore's neighbourhood, favouring
  the cell that minimises their BFS distance to their target exit.

  Speed distribution:  N(μ=1.34, σ=0.26) m/s  (based on Weidmann 1993
  pedestrian speed data, which the reference paper also cites).  At 30 cm
  resolution and a 0.5 s time-step this translates to ≈N(2.23, 0.43)
  cells/step.  A fractional movement accumulator allows non-integer speeds.

  Density slowdown:  local occupancy in a 3×3 neighbourhood above 0.5
  reduces an agent's effective speed proportionally, mirroring empirical
  fundamental-diagram relations (Fruin 1971, also used in the reference
  paper).

  Strategies:
    • Greedy  — always move toward the nearest exit (BFS distance).
    • Guided  — move toward the exit recommended by the route optimizer.
  An *adherence rate* ρ (default 0.70, matching the paper's baseline)
  controls the fraction of guided agents; the remaining 1-ρ fraction
  uses the greedy strategy even when guidance is available.

Outputs per time-step:
  positions, local density per cell, exit flow rates, congestion per
  region — used by Module 3 (dataset generator) and Module 7 (dashboard).
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .grid_map import GridMap, CellType, ExitPoint

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DT              = 0.5          # simulated seconds per step
SPEED_MEAN_MS   = 1.34         # m/s  (Weidmann 1993)
SPEED_STD_MS    = 0.26         # m/s
MAX_DENSITY     = 3.0          # agents per cell at maximum congestion
REGION_SIZE     = 8            # cells per side of each spatial region
MOORE_DIRS      = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
DIAG_COST       = math.sqrt(2)
CARD_COST       = 1.0

# ---------------------------------------------------------------------------
# BFS distance map
# ---------------------------------------------------------------------------

def compute_bfs_map(grid_arr: np.ndarray, exit_row: int, exit_col: int) -> np.ndarray:
    """
    Return a 2-D array of least-cost distances from every passable cell to
    (exit_row, exit_col).  Walls/obstacles have distance inf.

    Uses diagonal-aware BFS (cardinal cost 1, diagonal cost √2) so agents
    naturally take diagonal short-cuts, matching pedestrian behaviour.
    """
    H, W = grid_arr.shape
    dist = np.full((H, W), np.inf, dtype=np.float32)
    if not (0 <= exit_row < H and 0 <= exit_col < W):
        return dist
    dist[exit_row, exit_col] = 0.0
    q = deque()
    q.append((exit_row, exit_col))
    while q:
        r, c = q.popleft()
        for dr, dc in MOORE_DIRS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < H and 0 <= nc < W):
                continue
            cell = grid_arr[nr, nc]
            if cell == CellType.WALL or cell == CellType.OBSTACLE:
                continue
            cost = DIAG_COST if dr != 0 and dc != 0 else CARD_COST
            new_d = dist[r, c] + cost
            if new_d < dist[nr, nc]:
                dist[nr, nc] = new_d
                q.append((nr, nc))
    return dist


# ---------------------------------------------------------------------------
# Per-step record
# ---------------------------------------------------------------------------

@dataclass
class StepRecord:
    step:            int
    time_s:          float
    alive_count:     int
    exited_count:    int
    density_map:     np.ndarray          # shape (H, W)
    exit_flows:      Dict[int, int]      # exit_id → agents that exited this step
    region_stats:    List[Dict]          # one dict per region


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

class EvacuationSim:
    """
    Vectorised (numpy) agent-based simulation.

    Attributes
    ----------
    gm          : GridMap
    population  : int   number of agents placed
    adherence   : float fraction that follow guided strategy (0–1)
    rng         : numpy RandomState for reproducibility
    history     : list of StepRecord, one per step
    """

    def __init__(
        self,
        gm: GridMap,
        population: int,
        adherence_rate: float = 0.70,
        seed: Optional[int] = None,
        guided_exits: Optional[np.ndarray] = None,   # (N,) optional pre-set targets
    ):
        self.gm          = gm
        self.adherence   = float(np.clip(adherence_rate, 0.0, 1.0))
        self.rng         = np.random.default_rng(seed)
        self.history: List[StepRecord] = []
        self.step_num    = 0
        self.done        = False
        self._guided_exits = guided_exits  # updated by optimizer at runtime

        # Pre-compute grid as numpy array for fast indexing
        self._grid = np.array(self.gm.cells, dtype=np.int8)
        H, W = self._grid.shape
        self.H, self.W = H, W

        # Free cells for random agent placement
        free_mask = (self._grid == CellType.FREE)
        free_cells = np.argwhere(free_mask)
        max_pop = len(free_cells)
        population = min(int(population), max_pop)
        self.initial_population = population

        if population == 0 or len(self.gm.exits) == 0:
            raise ValueError("No agents or no exits — cannot simulate.")

        # Precompute BFS distance maps: shape (n_exits, H, W)
        n_exits = len(self.gm.exits)
        self.bfs_maps = np.stack([
            compute_bfs_map(self._grid, ex.row, ex.col)
            for ex in self.gm.exits
        ])  # (n_exits, H, W)

        # For greedy: assign each agent nearest exit at init
        # Place agents on random free cells
        chosen_idx = self.rng.choice(len(free_cells), size=population, replace=False)
        init_pos = free_cells[chosen_idx]  # (N, 2) [row, col]

        # Assign target exits (greedy = nearest)
        # For each agent, find exit with minimum bfs_map value
        agent_rows = init_pos[:, 0]
        agent_cols = init_pos[:, 1]
        dists_to_exits = self.bfs_maps[:, agent_rows, agent_cols]  # (n_exits, N)
        greedy_targets = np.argmin(dists_to_exits, axis=0)         # (N,)

        # Assign strategy: adherence_rate fraction are "guided"
        is_guided = self.rng.random(population) < self.adherence
        # Guided agents also start with greedy targets (overridden by optimizer each cycle)
        targets = greedy_targets.copy()

        # Walking speeds (m/s → cells/step)
        cells_per_step_mean = SPEED_MEAN_MS / (gm.resolution_cm / 100.0) * DT
        cells_per_step_std  = SPEED_STD_MS  / (gm.resolution_cm / 100.0) * DT
        raw_speeds = self.rng.normal(cells_per_step_mean, cells_per_step_std, population)
        speeds = np.clip(raw_speeds, 0.5, 5.0).astype(np.float32)

        # State arrays
        self.pos      = init_pos.astype(np.int16)     # (N, 2)
        self.speeds   = speeds                         # (N,)
        self.targets  = targets                        # (N,) exit index
        self.is_guided = is_guided                     # (N,) bool
        self.alive    = np.ones(population, dtype=bool)
        self.accum    = np.zeros(population, dtype=np.float32)   # movement accumulator
        self.exited_at: np.ndarray = np.full(population, -1, dtype=np.int32)

        # Region grid (for statistics)
        self.regions = self._build_regions()

        # Exit flow counters
        self.exit_flows_total = {i: 0 for i in range(n_exits)}

        # Initial density map
        self.density = np.zeros((H, W), dtype=np.int16)
        np.add.at(self.density, (self.pos[:, 0], self.pos[:, 1]), 1)

    # ------------------------------------------------------------------
    # Region bookkeeping
    # ------------------------------------------------------------------

    def _build_regions(self) -> List[Dict]:
        """Partition the grid into REGION_SIZE×REGION_SIZE blocks."""
        regions = []
        for r0 in range(0, self.H, REGION_SIZE):
            for c0 in range(0, self.W, REGION_SIZE):
                r1 = min(r0 + REGION_SIZE, self.H)
                c1 = min(c0 + REGION_SIZE, self.W)
                sub = self._grid[r0:r1, c0:c1]
                passable = int(np.sum(
                    (sub == CellType.FREE) | (sub == CellType.EXIT)
                ))
                if passable == 0:
                    continue
                # Nearest exit (by grid-centre BFS distance)
                cr, cc = (r0 + r1) // 2, (c0 + c1) // 2
                dists = [self.bfs_maps[i, cr, cc] for i in range(len(self.gm.exits))]
                nearest_exit = int(np.argmin(dists))
                nearest_dist = float(dists[nearest_exit])
                regions.append({
                    "id": len(regions),
                    "r0": r0, "c0": c0, "r1": r1, "c1": c1,
                    "passable": passable,
                    "center_row": cr, "center_col": cc,
                    "nearest_exit": nearest_exit,
                    "nearest_exit_dist": nearest_dist,
                })
        return regions

    # ------------------------------------------------------------------
    # Optimizer interface
    # ------------------------------------------------------------------

    def update_guided_targets(self, recommended: np.ndarray) -> None:
        """
        Called by the route optimizer every 30 s of simulated time.
        `recommended`: (N,) array of exit indices for all agents.
        Only guided (adherence) agents actually switch.
        """
        self.targets = np.where(self.is_guided, recommended, self.targets)

    def recommend_by_congestion(self, congestion_pred: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Compute recommended exit for every agent.
        effective_cost[i,e] = bfs_dist[e, pos[i]] × (1 + congestion_factor[e])

        If congestion_pred (n_exits,) is provided (from ML model), use it as
        the congestion factor.  Otherwise fall back to current density-based
        estimate.
        """
        alive_idx = np.where(self.alive)[0]
        recommended = self.targets.copy()
        if len(alive_idx) == 0:
            return recommended

        n_exits = len(self.gm.exits)

        # Default congestion = avg density near each exit
        if congestion_pred is None:
            congestion_pred = np.zeros(n_exits, dtype=np.float32)
            for ei, ex in enumerate(self.gm.exits):
                r0 = max(0, ex.row - 3); r1 = min(self.H, ex.row + 4)
                c0 = max(0, ex.col - 3); c1 = min(self.W, ex.col + 4)
                local_agents = int(self.density[r0:r1, c0:c1].sum())
                local_area   = (r1 - r0) * (c1 - c0)
                congestion_pred[ei] = local_agents / max(1.0, local_area)

        rows = self.pos[alive_idx, 0]
        cols = self.pos[alive_idx, 1]
        # dist: (n_exits, n_alive)
        dists = self.bfs_maps[:, rows, cols]   # (n_exits, n_alive)
        factors = 1.0 + congestion_pred[:, None]
        effective = dists * factors             # (n_exits, n_alive)
        best_exits = np.argmin(effective, axis=0)  # (n_alive,)
        recommended[alive_idx] = best_exits
        return recommended

    # ------------------------------------------------------------------
    # Single step
    # ------------------------------------------------------------------

    def step(self) -> StepRecord:
        """Advance simulation by one time-step DT seconds."""
        if self.done:
            return self.history[-1]

        alive_idx = np.where(self.alive)[0]
        n_alive = len(alive_idx)
        step_flows = {i: 0 for i in range(len(self.gm.exits))}

        # Accumulate movement
        self.accum[alive_idx] += self.speeds[alive_idx]

        # Process agents with accum >= 1 (shuffle for fairness)
        ready = alive_idx[self.accum[alive_idx] >= 1.0]
        order = self.rng.permutation(len(ready))
        ready = ready[order]

        # Claimed-cells set (prevent collision)
        claimed = set()

        for ai in ready:
            r, c = int(self.pos[ai, 0]), int(self.pos[ai, 1])
            target_exit = int(self.targets[ai])
            dist_map = self.bfs_maps[target_exit]

            # Density-based speed factor: look at 3×3 neighbourhood
            r0n = max(0, r-1); r1n = min(self.H, r+2)
            c0n = max(0, c-1); c1n = min(self.W, c+2)
            neighbours = int(self.density[r0n:r1n, c0n:c1n].sum())
            density_factor = max(0.05, 1.0 - (neighbours - 1) / (MAX_DENSITY * 9))

            if self.rng.random() > density_factor:
                continue   # agent stays put this step

            # Find best reachable neighbour
            best_r, best_c = r, c
            best_d = dist_map[r, c]

            for dr, dc in MOORE_DIRS:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.H and 0 <= nc < self.W):
                    continue
                cell = self._grid[nr, nc]
                if cell == CellType.WALL or cell == CellType.OBSTACLE:
                    continue
                if (nr, nc) in claimed:
                    continue
                d = dist_map[nr, nc]
                if d < best_d:
                    best_d = d
                    best_r, best_c = nr, nc

            if (best_r, best_c) != (r, c):
                claimed.add((best_r, best_c))
                self.density[r, c] -= 1
                self.pos[ai, 0] = best_r
                self.pos[ai, 1] = best_c
                self.density[best_r, best_c] += 1
                self.accum[ai] -= 1.0

                # Check exit
                if self._grid[best_r, best_c] == CellType.EXIT:
                    exit_id = target_exit
                    # Find actual exit id
                    for ei, ex in enumerate(self.gm.exits):
                        if ex.row == best_r and ex.col == best_c:
                            exit_id = ei
                            break
                    self.alive[ai] = False
                    self.exited_at[ai] = self.step_num
                    self.density[best_r, best_c] -= 1
                    step_flows[exit_id] = step_flows.get(exit_id, 0) + 1
                    self.exit_flows_total[exit_id] += 1
            else:
                self.accum[ai] = max(0.0, self.accum[ai] - 0.5)

        self.step_num += 1
        t = self.step_num * DT

        # Build density map snapshot
        density_snap = self.density.copy()

        # Compute region statistics
        region_stats = []
        alive_count = int(self.alive.sum())
        for reg in self.regions:
            r0, c0, r1, c1 = reg["r0"], reg["c0"], reg["r1"], reg["c1"]
            local_agents = int(self.density[r0:r1, c0:c1].sum())
            passable     = reg["passable"]
            density      = local_agents / max(1, passable)
            congestion   = min(1.0, density / MAX_DENSITY)
            # Average speed of agents in this region
            in_region = np.where(
                (self.alive) &
                (self.pos[:, 0] >= r0) & (self.pos[:, 0] < r1) &
                (self.pos[:, 1] >= c0) & (self.pos[:, 1] < c1)
            )[0]
            avg_speed = float(np.mean(self.speeds[in_region])) if len(in_region) else 0.0
            
            # Determine recommended exit for this region based on the agents' targets
            if len(in_region) > 0:
                targets_in_region = self.targets[in_region]
                recommended_exit_id = int(np.bincount(targets_in_region).argmax())
            else:
                recommended_exit_id = reg["nearest_exit"]

            region_stats.append({
                "region_id":           reg["id"],
                "center_row":          reg["center_row"],
                "center_col":          reg["center_col"],
                "local_population":    local_agents,
                "passable_cells":      passable,
                "local_density":       round(density, 4),
                "current_congestion":  round(congestion, 4),
                "nearest_exit_id":     reg["nearest_exit"],
                "nearest_exit_dist":   reg["nearest_exit_dist"],
                "avg_walking_speed":   round(avg_speed, 4),
                "recommended_exit_id": recommended_exit_id,
            })

        record = StepRecord(
            step=self.step_num,
            time_s=t,
            alive_count=alive_count,
            exited_count=self.initial_population - alive_count,
            density_map=density_snap,
            exit_flows=step_flows,
            region_stats=region_stats,
        )
        self.history.append(record)

        if alive_count == 0:
            self.done = True

        return record

    def run_to_completion(self, max_steps: int = 2000) -> int:
        """Run until all agents evacuate or max_steps reached. Returns steps taken."""
        while not self.done and self.step_num < max_steps:
            self.step()
        return self.step_num

    @property
    def evacuation_time_s(self) -> float:
        """Simulated evacuation time in seconds (or inf if not complete)."""
        if self.done:
            return self.step_num * DT
        last_exit = np.max(self.exited_at[self.exited_at >= 0]) if np.any(self.exited_at >= 0) else 0
        return float(last_exit) * DT

    def to_state_dict(self) -> Dict:
        """Serialisable snapshot for the live dashboard."""
        alive_pos = self.pos[self.alive]
        return {
            "step":         self.step_num,
            "time_s":       round(self.step_num * DT, 1),
            "alive_count":  int(self.alive.sum()),
            "exited_count": int((~self.alive).sum()),
            "done":         bool(self.done),
            "agents":       alive_pos.tolist(),
            "density_flat": self.density.flatten().tolist(),
            "exit_flows":   {str(k): v for k, v in self.exit_flows_total.items()},
            "region_congestion": [
                {"region_id": rs["region_id"],
                 "congestion": rs["current_congestion"],
                 "row": rs["center_row"],
                 "col": rs["center_col"],
                 "local_population": rs["local_population"],
                 "nearest_exit_id": rs["nearest_exit_id"],
                 "recommended_exit_id": rs.get("recommended_exit_id", rs["nearest_exit_id"])}
                for rs in (self.history[-1].region_stats if self.history else [])
            ],
        }
