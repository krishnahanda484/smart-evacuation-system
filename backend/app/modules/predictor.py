"""
Module 5 — Congestion Prediction Service & Dynamic Route Optimizer
====================================================================
Wraps the trained ML model and implements the effective-path-length
route optimizer described in the reference paper (Eq. 2).

  L_eff(i, e) = d_BFS(i, e) × (1 + α × ĉ(e))

At each update cycle (every 30 simulated seconds) the optimizer also
computes per-zone directional recommendations and detects rerouting
events — when a zone's nearest exit is congested above CONGESTION_THRESHOLD
and a different exit is recommended instead.  These are surfaced as live
visual arrows and alert messages on the dashboard.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

DATA_DIR         = Path(__file__).parent.parent.parent / "data"
CONGESTION_MODEL = DATA_DIR / "best_congestion_model.pkl"

ALPHA               = 2.0    # congestion weight in effective path length
UPDATE_INTERVAL_S   = 30.0   # simulated seconds between optimizer calls
CONGESTION_THRESHOLD = 0.60  # predicted congestion level that triggers rerouting alert


class CongestionPredictor:
    """Loads and wraps the best trained congestion model. Thread-safe for inference."""

    def __init__(self):
        self._model_bundle = None
        self._model_name   = "none"
        self._loaded_at    = 0.0

    def load(self) -> bool:
        import joblib
        if not CONGESTION_MODEL.exists():
            return False
        self._model_bundle = joblib.load(CONGESTION_MODEL)
        self._model_name   = self._model_bundle.get("name", "unknown")
        self._loaded_at    = time.time()
        return True

    @property
    def is_loaded(self) -> bool:
        return self._model_bundle is not None

    @property
    def model_name(self) -> str:
        return self._model_name

    def predict_congestion(self, features: np.ndarray) -> np.ndarray:
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        bundle = self._model_bundle
        model  = bundle["model"]
        name   = bundle["name"]
        if name == "mlp":
            model_obj, scaler = model
            X = scaler.transform(features)
            return np.clip(model_obj.predict(X), 0.0, 1.0).astype(np.float32)
        return np.clip(model.predict(features), 0.0, 1.0).astype(np.float32)


_predictor = CongestionPredictor()


def get_predictor() -> CongestionPredictor:
    if not _predictor.is_loaded:
        _predictor.load()
    return _predictor


# ---------------------------------------------------------------------------
# Route optimizer
# ---------------------------------------------------------------------------

class RouteOptimizer:
    """
    Computes recommended exits using ML-predicted congestion.
    Also builds per-zone directional guidance and rerouting event messages.
    """

    def __init__(self, sim, predictor: Optional[CongestionPredictor] = None):
        self.sim             = sim
        self.predictor       = predictor or get_predictor()
        self._last_update_s  = -999.0
        self._zone_directions: List[Dict] = []
        self._reroute_events: List[str]   = []

    def should_update(self) -> bool:
        current_t = self.sim.step_num * 0.5
        return (current_t - self._last_update_s) >= UPDATE_INTERVAL_S

    def recommend(self) -> np.ndarray:
        """Backward-compat wrapper — delegates to recommend_with_zones."""
        recommended, _, _ = self.recommend_with_zones()
        return recommended

    def recommend_with_zones(self) -> Tuple[np.ndarray, List[Dict], List[str]]:
        """
        Compute ML-guided routing for every alive agent.
        Returns:
          recommended      (N,) exit indices for all agents
          zone_directions  list of per-region dicts with direction info
          reroute_events   list of human-readable alert strings
        """
        if not self.sim.alive.any():
            return self.sim.targets.copy(), [], []

        n_exits = len(self.sim.gm.exits)
        congestion_by_exit = self._predict_exit_congestion()  # (n_exits,)

        # ── Per-agent effective-path routing ────────────────────────────
        alive_idx = np.where(self.sim.alive)[0]
        rows = self.sim.pos[alive_idx, 0]
        cols = self.sim.pos[alive_idx, 1]
        dists   = self.sim.bfs_maps[:, rows, cols]          # (n_exits, n_alive)
        factors = 1.0 + ALPHA * congestion_by_exit[:, None] # (n_exits, 1)
        effective = dists * factors                          # (n_exits, n_alive)
        best     = np.argmin(effective, axis=0)             # (n_alive,)
        recommended = self.sim.targets.copy()
        recommended[alive_idx] = best

        # ── Per-zone directional guidance ────────────────────────────────
        zone_directions: List[Dict] = []
        reroute_events: List[str]   = []

        for reg in self.sim.regions:
            cr, cc = reg["center_row"], reg["center_col"]
            # Effective cost from this region's centre to each exit
            dists_for_center = self.sim.bfs_maps[:, cr, cc]   # (n_exits,)
            eff_center = dists_for_center * (1.0 + ALPHA * congestion_by_exit)
            recommended_exit = int(np.argmin(eff_center))
            nearest_exit     = reg["nearest_exit"]
            is_rerouted      = recommended_exit != nearest_exit
            nc = float(congestion_by_exit[nearest_exit])

            zone_directions.append({
                "region_id":        reg["id"],
                "center_row":       cr,
                "center_col":       cc,
                "recommended_exit": recommended_exit,
                "nearest_exit":     nearest_exit,
                "is_rerouted":      is_rerouted,
                "exit_congestion":  round(nc, 3),
            })

            if is_rerouted and nc > CONGESTION_THRESHOLD:
                exit_info = self.sim.gm.exits
                rec_pos = (
                    f"({exit_info[recommended_exit].row},{exit_info[recommended_exit].col})"
                    if recommended_exit < len(exit_info) else str(recommended_exit)
                )
                reroute_events.append(
                    f"Exit {nearest_exit} congested ({nc:.0%}) — "
                    f"zone [{cr},{cc}] rerouted → Exit {recommended_exit} {rec_pos}"
                )

        self._zone_directions = zone_directions
        self._reroute_events  = reroute_events
        self._last_update_s   = self.sim.step_num * 0.5
        return recommended, zone_directions, reroute_events

    def _predict_exit_congestion(self) -> np.ndarray:
        """Return (n_exits,) predicted congestion near each exit."""
        n_exits = len(self.sim.gm.exits)

        if not self.predictor.is_loaded:
            # Fallback: current density near each exit
            c = np.zeros(n_exits, dtype=np.float32)
            for ei, ex in enumerate(self.sim.gm.exits):
                r0 = max(0, ex.row - 4); r1 = min(self.sim.H, ex.row + 5)
                c0 = max(0, ex.col - 4); c1 = min(self.sim.W, ex.col + 5)
                local = int(self.sim.density[r0:r1, c0:c1].sum())
                area  = max(1, (r1-r0)*(c1-c0))
                c[ei] = min(1.0, local / (area * 0.5))
            return c

        from .ml_train import FEATURE_COLS
        if not self.sim.history:
            return np.zeros(n_exits, dtype=np.float32)

        last_stats = {rs["region_id"]: rs for rs in self.sim.history[-1].region_stats}

        exit_features = np.zeros((n_exits, len(FEATURE_COLS)), dtype=np.float32)
        for ei, ex in enumerate(self.sim.gm.exits):
            best_reg = min(self.sim.regions, key=lambda r: (
                (r["center_row"]-ex.row)**2 + (r["center_col"]-ex.col)**2
            ))
            rs = last_stats.get(best_reg["id"], {})
            feat = {
                "population_total":   self.sim.initial_population,
                "adherence_rate":     self.sim.adherence,
                "timestamp_s":        self.sim.step_num * 0.5,
                "local_population":   rs.get("local_population", 0),
                "passable_cells":     rs.get("passable_cells", best_reg["passable"]),
                "local_density":      rs.get("local_density", 0),
                "nearest_exit_dist":  best_reg["nearest_exit_dist"],
                "exit_flow_this_step":sum(self.sim.history[-1].exit_flows.values()),
                "avg_walking_speed":  rs.get("avg_walking_speed", 2.23),
                "current_congestion": rs.get("current_congestion", 0),
            }
            for fi, col in enumerate(FEATURE_COLS):
                exit_features[ei, fi] = feat.get(col, 0.0)

        return self.predictor.predict_congestion(exit_features)
