"""Priority 1: paired seeded Monte Carlo action comparisons, not a trained model."""

from datetime import datetime, timezone

import numpy as np

from baselhack.interfaces import Action
from baselhack.simulator.journey import simulate
from baselhack.simulator.river import barge_factor


def analyze(scenario, n_runs=None):
    n = scenario["thresholds"]["monte_carlo_runs"] if n_runs is None else n_runs
    if n < 1:
        raise ValueError("n_runs must be positive")
    per_action = {}
    baseline = []
    suspended = (
        barge_factor(scenario, datetime.fromisoformat(scenario["start_at"])) is None
    )
    for action in Action:
        if action in (Action.BUFFER, Action.QUARANTINE):
            stock = scenario["site"]["stock_batches"]
            required = scenario["site"]["batch_stock_required"]
            covered = stock >= required
            results = [
                {
                    **r,
                    "stock_after": stock - required if covered else stock,
                    "batch_delay_min": 0.0
                    if covered
                    else scenario["thresholds"]["suspension_delay_min"],
                }
                for r in baseline
            ]
        else:
            results = [
                simulate(scenario, scenario["seed"] + i, action, record=False)
                for i in range(n)
            ]
        if action == Action.RUN_AS_PLANNED:
            baseline = results
        eligible = True
        reason = "Eligible simulation variant"
        if (
            action in (Action.BUFFER, Action.QUARANTINE)
            and scenario["site"]["stock_batches"]
            < scenario["site"]["batch_stock_required"]
        ):
            eligible = action == Action.QUARANTINE
            reason = "Stock does not cover the batch"
        if action == Action.EXPEDITE and suspended:
            eligible = False
            reason = "The route is suspended; a faster slot on the same route cannot resolve it"
        per_action[str(action)] = {
            "exp_delay_min": float(np.mean([r["batch_delay_min"] for r in results])),
            "p_miss_slot": float(np.mean([r["batch_delay_min"] > 0 for r in results])),
            "p_excursion": float(np.mean([r["budget_used"] > 1 for r in results])),
            "stock_after": results[0]["stock_after"],
            "eligible": eligible,
            "reason": reason,
        }
    etas = [datetime.fromisoformat(r["eta"]).timestamp() for r in baseline if r["eta"]]

    def quantile(q):
        return (
            datetime.fromtimestamp(
                float(np.quantile(etas, q)),
                timezone.utc,
            ).isoformat()
            if etas
            else None
        )

    first = per_action["RUN_AS_PLANNED"]
    return {
        "scenario_id": scenario["scenario_id"],
        "n_runs": n,
        "eta_p50": quantile(0.5),
        "eta_p90": quantile(0.9),
        "p_miss_slot": first["p_miss_slot"],
        "p_excursion": first["p_excursion"],
        "per_action": per_action,
        "gauge_flags": [],
        "river_forecast": [],
        "model": "Monte Carlo on ASSUMED simulation; not validated real-world probabilities",
        "sources": {
            "per_action": f"decision_analysis: {n} paired seeded simulated journeys per action",
            "eta": "Monte Carlo quantiles; conditional on route completion; null if suspended",
            "gauge_flags": "not evaluated; optional priority 3",
            "river_forecast": "not trained; TODO(verify): long history and persistence comparison",
        },
    }
