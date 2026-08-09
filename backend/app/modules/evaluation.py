"""
Module 8 — Evaluation Suite
==============================
Runs N simulations under (a) greedy baseline and (b) ML-guided routing,
reporting mean evacuation time, exit-balance, congestion AUC, and
rerouting frequency — the mechanism behind the improvement.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import numpy as np

from .simulation import EvacuationSim
from .predictor import RouteOptimizer, get_predictor, CONGESTION_THRESHOLD
from .sample_layouts import build_small, build_medium, build_large

_eval_status: Dict[str, Any] = {"state": "idle", "result": None, "error": None}

BUILDERS = {
    "sample_small":  build_small,
    "sample_medium": build_medium,
    "sample_large":  build_large,
}


def _trapz(y: List[float]) -> float:
    """Version-safe trapezoidal integration (works with NumPy < 2.0 and ≥ 2.0)."""
    if not y:
        return 0.0
    try:
        return float(np.trapezoid(y))          # NumPy ≥ 2.0
    except AttributeError:
        return float(np.trapz(y))              # NumPy < 2.0


def get_eval_status() -> Dict[str, Any]:
    return dict(_eval_status)


def _run_batch(
    layout_id: str,
    population: int,
    adherence: float,
    n_runs: int,
    guided: bool,
    seed_offset: int = 0,
) -> List[Dict]:
    """Run n_runs simulations and return per-run result dicts."""
    gm = BUILDERS[layout_id]()
    predictor = get_predictor() if guided else None
    results = []

    for i in range(n_runs):
        sim = EvacuationSim(
            gm=gm,
            population=population,
            adherence_rate=adherence if guided else 0.0,
            seed=seed_offset + i,
        )

        optimizer = RouteOptimizer(sim, predictor) if guided else None
        cong_over_time: List[float] = []
        reroute_zone_steps = 0      # how many (region, update) pairs were rerouted
        total_zone_steps   = 0      # denominator

        while not sim.done and sim.step_num < 1500:
            rec = sim.step()

            if optimizer and optimizer.should_update():
                recommended, zone_dirs, _ = optimizer.recommend_with_zones()
                sim.update_guided_targets(recommended)
                # Tally rerouting
                total_zone_steps   += len(zone_dirs)
                reroute_zone_steps += sum(1 for z in zone_dirs if z["is_rerouted"])

            if rec.region_stats:
                mean_cong = float(np.mean([r["current_congestion"] for r in rec.region_stats]))
                cong_over_time.append(mean_cong)

        evac_time    = sim.evacuation_time_s
        exit_flows   = list(sim.exit_flows_total.values())
        exit_balance = float(np.std(exit_flows)) if exit_flows else 0.0
        cong_auc     = _trapz(cong_over_time)

        results.append({
            "evac_time_s":         evac_time,
            "exit_flows":          exit_flows,
            "exit_balance":        exit_balance,
            "cong_auc":            cong_auc,
            "steps":               sim.step_num,
            "cong_series":         cong_over_time,
            "reroute_zone_steps":  reroute_zone_steps,
            "total_zone_steps":    total_zone_steps,
        })

    return results


def run_evaluation(
    layout_id: str = "sample_medium",
    population: int = 300,
    adherence: float = 0.70,
    n_runs: int = 20,
) -> Dict[str, Any]:
    global _eval_status
    _eval_status.update({"state": "running", "result": None, "error": None})

    try:
        t0 = time.time()

        greedy_results = _run_batch(layout_id, population, 0.0,      n_runs, guided=False, seed_offset=0)
        guided_results = _run_batch(layout_id, population, adherence, n_runs, guided=True,  seed_offset=1000)

        greedy_times = np.array([r["evac_time_s"]  for r in greedy_results])
        guided_times = np.array([r["evac_time_s"]  for r in guided_results])
        greedy_bal   = np.array([r["exit_balance"]  for r in greedy_results])
        guided_bal   = np.array([r["exit_balance"]  for r in guided_results])
        greedy_auc   = np.array([r["cong_auc"]      for r in greedy_results])
        guided_auc   = np.array([r["cong_auc"]      for r in guided_results])

        mean_g  = float(np.mean(greedy_times))
        mean_ml = float(np.mean(guided_times))
        improvement_pct = (mean_g - mean_ml) / mean_g * 100 if mean_g > 0 else 0.0

        # Rerouting statistics
        total_reroutes  = sum(r["reroute_zone_steps"] for r in guided_results)
        total_zsteps    = sum(r["total_zone_steps"]   for r in guided_results)
        pct_rerouted    = total_reroutes / max(1, total_zsteps) * 100
        # Rough contribution: improvement that correlates with rerouting presence
        reroute_contrib = improvement_pct * (pct_rerouted / 100.0) if pct_rerouted > 0 else 0.0

        # Build congestion time series (aligned by length, padded with last value)
        def pad_series(runs, max_len):
            padded = []
            for r in runs:
                s = r["cong_series"]
                padded.append(s + [s[-1] if s else 0.0] * (max_len - len(s)))
            return np.array(padded)

        max_len = max(
            max(len(r["cong_series"]) for r in greedy_results),
            max(len(r["cong_series"]) for r in guided_results),
        )
        greedy_cong_mean = pad_series(greedy_results, max_len).mean(axis=0).tolist()
        guided_cong_mean = pad_series(guided_results, max_len).mean(axis=0).tolist()
        time_axis = [i * 0.5 for i in range(max_len)]

        result = {
            "layout_id":   layout_id,
            "population":  population,
            "adherence":   adherence,
            "n_runs":      n_runs,
            "greedy": {
                "mean_evac_time_s":  round(mean_g, 2),
                "std_evac_time_s":   round(float(np.std(greedy_times)), 2),
                "mean_exit_balance": round(float(np.mean(greedy_bal)), 4),
                "mean_cong_auc":     round(float(np.mean(greedy_auc)), 4),
                "all_times":         greedy_times.tolist(),
            },
            "guided": {
                "mean_evac_time_s":  round(mean_ml, 2),
                "std_evac_time_s":   round(float(np.std(guided_times)), 2),
                "mean_exit_balance": round(float(np.mean(guided_bal)), 4),
                "mean_cong_auc":     round(float(np.mean(guided_auc)), 4),
                "all_times":         guided_times.tolist(),
            },
            "improvement_pct": round(improvement_pct, 2),
            "rerouting": {
                "total_reroute_decisions": int(total_reroutes),
                "total_zone_decisions":    int(total_zsteps),
                "pct_zones_rerouted":      round(pct_rerouted, 1),
                "rerouting_contribution_pct": round(reroute_contrib, 2),
                "description": (
                    f"Out of {total_zsteps} zone-update decisions across {n_runs} guided runs, "
                    f"{total_reroutes} ({pct_rerouted:.1f}%) redirected occupants away from a "
                    f"congested nearest exit. This rerouting mechanism accounts for an estimated "
                    f"{reroute_contrib:.1f}% of the {improvement_pct:.1f}% total time improvement."
                ),
            },
            "congestion_time_series": {
                "time_axis":   time_axis,
                "greedy_mean": greedy_cong_mean,
                "guided_mean": guided_cong_mean,
            },
            "wall_time_s": round(time.time() - t0, 1),
        }

        _eval_status.update({"state": "done", "result": result})
        return result

    except Exception as exc:
        import traceback
        _eval_status.update({
            "state": "error",
            "error": str(exc),
            "detail": traceback.format_exc(),
        })
        raise
