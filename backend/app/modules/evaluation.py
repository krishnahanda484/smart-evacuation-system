"""
Module 8 — Evaluation Suite
==============================
Reproduces the reference paper's evaluation methodology: for the same
layout and population, runs N simulations under (a) greedy baseline and
(b) ML-guided periodic prediction, then reports:

  • Mean evacuation time improvement  Δt% = (t_greedy - t_guided) / t_greedy × 100
  • Exit utilisation balance          σ(exit_flows) — lower is more balanced
  • Congestion-over-time AUC          area under the mean-congestion curve

Target benchmark: ~21 % improvement as reported by Ibrahim et al. (2023).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import numpy as np

from .simulation import EvacuationSim
from .predictor import RouteOptimizer, get_predictor
from .sample_layouts import build_small, build_medium, build_large

_eval_status: Dict[str, Any] = {"state": "idle", "result": None, "error": None}

BUILDERS = {
    "sample_small":  build_small,
    "sample_medium": build_medium,
    "sample_large":  build_large,
}


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
        cong_over_time = []

        while not sim.done and sim.step_num < 1500:
            rec = sim.step()

            # Update guided targets every 30 s of simulated time
            if optimizer and optimizer.should_update():
                recommended = optimizer.recommend()
                sim.update_guided_targets(recommended)

            # Log mean congestion this step
            if rec.region_stats:
                mean_cong = float(np.mean([r["current_congestion"] for r in rec.region_stats]))
                cong_over_time.append(mean_cong)

        evac_time = sim.evacuation_time_s
        exit_flows = list(sim.exit_flows_total.values())
        exit_balance = float(np.std(exit_flows)) if exit_flows else 0.0
        cong_auc = float(np.trapz(cong_over_time)) if cong_over_time else 0.0

        results.append({
            "evac_time_s":   evac_time,
            "exit_flows":    exit_flows,
            "exit_balance":  exit_balance,
            "cong_auc":      cong_auc,
            "steps":         sim.step_num,
            "cong_series":   cong_over_time,
        })

    return results


def run_evaluation(
    layout_id: str = "sample_medium",
    population: int = 300,
    adherence: float = 0.70,
    n_runs: int = 20,
) -> Dict[str, Any]:
    """
    Run the full A/B evaluation: greedy vs. ML-guided.
    Blocks until complete — run in a thread.
    """
    global _eval_status
    _eval_status.update({"state": "running", "result": None, "error": None})

    try:
        t0 = time.time()

        greedy_results  = _run_batch(layout_id, population, 0.0,      n_runs, guided=False, seed_offset=0)
        guided_results  = _run_batch(layout_id, population, adherence, n_runs, guided=True,  seed_offset=1000)

        greedy_times  = np.array([r["evac_time_s"]  for r in greedy_results])
        guided_times  = np.array([r["evac_time_s"]  for r in guided_results])
        greedy_bal    = np.array([r["exit_balance"]  for r in greedy_results])
        guided_bal    = np.array([r["exit_balance"]  for r in guided_results])
        greedy_auc    = np.array([r["cong_auc"]      for r in greedy_results])
        guided_auc    = np.array([r["cong_auc"]      for r in guided_results])

        mean_g  = float(np.mean(greedy_times))
        mean_ml = float(np.mean(guided_times))
        improvement_pct = (mean_g - mean_ml) / mean_g * 100 if mean_g > 0 else 0.0

        # Build congestion time series (aligned by length, padded with zeros)
        def pad_series(runs, max_len):
            padded = [r["cong_series"] + [0.0] * (max_len - len(r["cong_series"])) for r in runs]
            return np.array(padded)

        max_len = max(max(len(r["cong_series"]) for r in greedy_results),
                      max(len(r["cong_series"]) for r in guided_results))
        greedy_cong_mean = pad_series(greedy_results, max_len).mean(axis=0).tolist()
        guided_cong_mean = pad_series(guided_results, max_len).mean(axis=0).tolist()
        time_axis = [i * 0.5 for i in range(max_len)]

        result = {
            "layout_id":     layout_id,
            "population":    population,
            "adherence":     adherence,
            "n_runs":        n_runs,
            "greedy": {
                "mean_evac_time_s": round(mean_g, 2),
                "std_evac_time_s":  round(float(np.std(greedy_times)), 2),
                "mean_exit_balance":round(float(np.mean(greedy_bal)), 4),
                "mean_cong_auc":    round(float(np.mean(greedy_auc)), 4),
                "all_times":        greedy_times.tolist(),
            },
            "guided": {
                "mean_evac_time_s": round(mean_ml, 2),
                "std_evac_time_s":  round(float(np.std(guided_times)), 2),
                "mean_exit_balance":round(float(np.mean(guided_bal)), 4),
                "mean_cong_auc":    round(float(np.mean(guided_auc)), 4),
                "all_times":        guided_times.tolist(),
            },
            "improvement_pct":       round(improvement_pct, 2),
            "congestion_time_series": {
                "time_axis":   time_axis,
                "greedy_mean": greedy_cong_mean,
                "guided_mean": guided_cong_mean,
            },
            "wall_time_s":   round(time.time() - t0, 1),
        }

        _eval_status.update({"state": "done", "result": result})
        return result

    except Exception as exc:
        import traceback
        _eval_status.update({"state": "error", "error": str(exc),
                             "detail": traceback.format_exc()})
        raise
