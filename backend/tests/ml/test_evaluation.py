"""Metric and baseline tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.evaluation import (
    baseline_metrics,
    best_baseline,
    evaluate,
    improvement_over,
)

pytestmark = pytest.mark.ml


def test_perfect_prediction_scores_zero_error() -> None:
    values = np.array([10.0, 20.0, 30.0])
    metrics = evaluate(values, values)
    assert metrics.mae == 0
    assert metrics.rmse == 0
    assert metrics.mape == 0
    assert metrics.r2 == 1.0


def test_metrics_are_computed_correctly() -> None:
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 18.0, 33.0])
    metrics = evaluate(y_true, y_pred)
    assert metrics.mae == pytest.approx(7 / 3, abs=0.001)
    assert metrics.rmse == pytest.approx(np.sqrt((4 + 4 + 9) / 3), abs=0.001)
    assert metrics.n == 3


def test_mape_ignores_zero_actuals() -> None:
    metrics = evaluate(np.array([0.0, 10.0]), np.array([5.0, 11.0]))
    # Only the non zero actual contributes: |11-10|/10 = 10%
    assert metrics.mape == pytest.approx(10.0, abs=0.01)
    assert metrics.smape is not None


def test_mape_is_none_when_all_actuals_are_zero() -> None:
    metrics = evaluate(np.array([0.0, 0.0]), np.array([1.0, 2.0]))
    assert metrics.mape is None


def test_bias_shows_systematic_under_forecasting() -> None:
    metrics = evaluate(np.array([10.0, 10.0]), np.array([6.0, 6.0]))
    assert metrics.bias == -4.0


def test_baselines_are_evaluated() -> None:
    frame = pd.DataFrame(
        {
            "revenue": [10.0, 12.0, 11.0, 13.0],
            "revenue_lag_1": [9.0, 10.0, 12.0, 11.0],
            "revenue_lag_7": [8.0, 9.0, 10.0, 12.0],
            "revenue_roll_mean_7": [9.5, 10.5, 11.0, 12.0],
        }
    )
    results = baseline_metrics(frame, "revenue")
    assert set(results) == {
        "naive_last_value",
        "seasonal_naive_7d",
        "moving_average_7d",
    }
    name, values = best_baseline(results)
    assert name in results
    assert values["mae"] == min(row["mae"] for row in results.values())


def test_improvement_is_positive_when_model_wins() -> None:
    model = evaluate(np.array([10.0, 10.0]), np.array([10.5, 9.5]))
    baseline = {"mae": 2.0, "rmse": 2.0}
    result = improvement_over(model, baseline)
    assert result["mae_improvement_percent"] > 0
