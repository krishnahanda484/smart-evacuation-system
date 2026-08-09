"""
Module 5 — Congestion Prediction Service & Dynamic Route Optimizer
====================================================================
Wraps the trained ML model and implements the effective-path-length
route optimizer described in the reference paper (Eq. 2).

Design rationale (for methodology section):
  At runtime the route optimizer is called every 30 simulated seconds
  (= 60 time-steps).  For each region it submits the current feature
  vector to the trained model and obtains a predicted congestion value
  30 s ahead.  The effective path length for exit e from agent i is:

      L_eff(i, e) = d_BFS(i, e)  ×  (1 + α × ĉ(e))

  where d_BFS is the BFS distance in cells, ĉ(e) is the ML-predicted
  mean congestion of the cells along the path to exit e (approximated
  here by the predicted congestion of the region nearest to e), and α
  is a scaling factor (default 2.0, empirically tuned).

  This replaces the Monte-Carlo forecasting loop used by Ibrahim et al.:
  instead of running 100+ fresh simulations per prediction cycle, we do a
  single forward pass through the trained model (microseconds vs seconds),
  enabling real-time guidance updates.

  Fallback: if no trained model is available the optimizer falls back to
  the plain BFS distance (α = 0), equivalent to the greedy strategy.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

DATA_DIR         = Path(__file__).parent.parent.parent / "data"
CONGESTION_MODEL = DATA_DIR / "best_congestion_model.pkl"

ALPHA = 2.0          # congestion weight in effective path length
UPDATE_INTERVAL_S = 30.0   # simulated seconds between optimizer calls


class CongestionPredictor:
    """
    Loads and wraps the best trained congestion model.
    Thread-safe for read-only inference.
    """

    def __init__(self):
        self._model_bundle = None
        self._model_name   = "none"
        self._loaded_at    = 0.0

    def load(self) -> bool:
        """Load (or reload) the model from disk. Returns True if successful."""
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

    def predict_congestion(
        self,
        features: np.ndarray,   # shape (n_regions, n_features)
    ) -> np.ndarray:
        """
        Return predicted congestion_in_30s for each row in `features`.
        Shape: (n_regions,)
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        bundle = self._model_bundle
        model  = bundle["model"]
        name   = bundle["name"]

        if name == "mlp":
            # MLP needs StandardScaler applied first
            model_obj, scaler = model
            X = scaler.transform(features)
            return np.clip(model_obj.predict(X), 0.0, 1.0).astype(np.float32)
        else:
            return np.clip(model.predict(features), 0.0, 1.0).astype(np.float32)


# Singleton
_predictor = CongestionPredictor()


def get_predictor() -> CongestionPredictor:
    """Return the singleton predictor, loading the model if not yet loaded."""
    if not _predictor.is_loaded:
        _predictor.load()
    return _predictor


# ---------------------------------------------------------------------------
# Route optimizer
# ---------------------------------------------------------------------------

class RouteOptimizer:
    """
    Computes recommended exits for all alive agents using ML-predicted
    congestion via the effective-path-length formula.

    Usage:
        optimizer = RouteOptimizer(sim)
        recommended = optimizer.recommend()   # (N,) exit indices
        sim.update_guided_targets(recommended)
    """

    def __init__(self, sim, predictor: Optional[CongestionPredictor] = None):
        self.sim       = sim
        self.predictor = predictor or get_predictor()
        self._last_update_s = -999.0
        self._last_recommended: Optional[np.ndarray] = None

    def should_update(self) -> bool:
        current_t = self.sim.step_num * 0.5  # simulated seconds
        return (current_t - self._last_update_s) >= UPDATE_INTERVAL_S

    def recommend(self) -> np.ndarray:
        """
        Compute effective-path-length routing for every alive agent.
        Returns (N,) array of recommended exit indices.
        """
        if not self.sim.alive.any():
            return self.sim.targets.copy()

        n_exits = len(self.sim.gm.exits)

        # Predict congestion for each exit's surrounding region
        congestion_by_exit = self._predict_exit_congestion()

        # effective_cost[agent_i, exit_e] = bfs_dist × (1 + α × cong)
        alive_idx = np.where(self.sim.alive)[0]
        rows = self.sim.pos[alive_idx, 0]
        cols = self.sim.pos[alive_idx, 1]

        dists = self.sim.bfs_maps[:, rows, cols]   # (n_exits, n_alive)
        factors = 1.0 + ALPHA * congestion_by_exit[:, None]  # (n_exits, 1) broadcast
        effective = dists * factors

        best = np.argmin(effective, axis=0)   # (n_alive,)
        recommended = self.sim.targets.copy()
        recommended[alive_idx] = best

        self._last_recommended = recommended
        self._last_update_s = self.sim.step_num * 0.5
        return recommended

    def _predict_exit_congestion(self) -> np.ndarray:
        """
        Return (n_exits,) array of predicted congestion near each exit.
        Falls back to density-based estimate if model not available.
        """
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

        # Build feature vectors for each exit's region
        from .ml_train import FEATURE_COLS
        n_exits = len(self.sim.gm.exits)
        if not self.sim.history:
            return np.zeros(n_exits, dtype=np.float32)

        last_stats = {rs["region_id"]: rs for rs in self.sim.history[-1].region_stats}

        # Map each exit to its nearest region
        exit_features = np.zeros((n_exits, len(FEATURE_COLS)), dtype=np.float32)
        for ei, ex in enumerate(self.sim.gm.exits):
            # Find nearest region by exit position
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
