"""Priority 4 skeleton: persistence baseline before model promotion."""

import numpy as np


def persistence_score(values, horizon_steps):
    if horizon_steps < 1 or len(values) <= horizon_steps:
        raise ValueError("TODO(verify): insufficient history for forecast evaluation")
    values = np.asarray(values, dtype=float)
    return {
        "persistence_mae_cm": float(
            np.mean(np.abs(values[horizon_steps:] - values[:-horizon_steps]))
        ),
        "model_mae_cm": None,
        "status": "TODO(verify): train model on verified history and chronological holdout",
    }
