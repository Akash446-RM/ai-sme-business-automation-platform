"""Evaluation metrics and naive baselines.

A model is only worth deploying if it beats a trivial rule. Every trained
model in this project is reported alongside three baselines so the measured
improvement is explicit and honest.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass
class Metrics:
    """Standard regression metrics for forecasting."""

    mae: float
    rmse: float
    mape: Optional[float]
    smape: float
    r2: Optional[float]
    bias: float
    n: int

    def to_dict(self) -> Dict[str, Optional[float]]:
        return asdict(self)


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> Metrics:
    """Compute forecasting metrics.

    MAPE is undefined when actuals contain zeros, which is common for product
    level demand. It is reported only over non zero actuals and sMAPE is always
    reported as a zero safe alternative.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    bias = float(np.mean(errors))

    non_zero = y_true != 0
    mape = (
        float(np.mean(np.abs(errors[non_zero] / y_true[non_zero])) * 100)
        if non_zero.any()
        else None
    )

    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2
    safe = denominator != 0
    smape = (
        float(np.mean(np.abs(errors[safe]) / denominator[safe]) * 100) if safe.any() else 0.0
    )

    variance = float(np.var(y_true))
    r2 = float(1 - np.mean(errors**2) / variance) if variance > 0 else None

    return Metrics(
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        mape=round(mape, 2) if mape is not None else None,
        smape=round(smape, 2),
        r2=round(r2, 4) if r2 is not None else None,
        bias=round(bias, 4),
        n=int(len(y_true)),
    )


def naive_baseline(frame: pd.DataFrame, target: str) -> np.ndarray:
    """Predict yesterday's value."""
    return frame[f"{target}_lag_1"].to_numpy(dtype=float)


def seasonal_naive_baseline(frame: pd.DataFrame, target: str) -> np.ndarray:
    """Predict the value from the same weekday last week."""
    return frame[f"{target}_lag_7"].to_numpy(dtype=float)


def moving_average_baseline(frame: pd.DataFrame, target: str, window: int = 7) -> np.ndarray:
    """Predict the trailing mean."""
    return frame[f"{target}_roll_mean_{window}"].to_numpy(dtype=float)


def baseline_metrics(frame: pd.DataFrame, target: str) -> Dict[str, Dict]:
    """Evaluate all three baselines on the supplied evaluation frame."""
    y_true = frame[target].to_numpy(dtype=float)
    results: Dict[str, Dict] = {}
    candidates = {
        "naive_last_value": naive_baseline,
        "seasonal_naive_7d": seasonal_naive_baseline,
        "moving_average_7d": moving_average_baseline,
    }
    for name, function in candidates.items():
        try:
            predictions = np.nan_to_num(function(frame, target), nan=0.0)
        except KeyError:
            continue
        results[name] = evaluate(y_true, predictions).to_dict()
    return results


def improvement_over(model: Metrics, baseline: Dict[str, float]) -> Dict[str, float]:
    """Percentage error reduction relative to a baseline (positive is better)."""
    result: Dict[str, float] = {}
    for metric in ("mae", "rmse"):
        base_value = baseline.get(metric)
        model_value = getattr(model, metric)
        if base_value:
            result[f"{metric}_improvement_percent"] = round(
                (base_value - model_value) / base_value * 100, 2
            )
    return result


def best_baseline(baselines: Dict[str, Dict], metric: str = "mae") -> tuple[str, Dict]:
    """Return the strongest baseline, which is what a model must beat."""
    name = min(baselines, key=lambda key: baselines[key].get(metric, float("inf")))
    return name, baselines[name]
