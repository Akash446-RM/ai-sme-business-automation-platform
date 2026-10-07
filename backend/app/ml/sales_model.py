"""Business level sales (revenue) forecasting model.

Algorithm choice
----------------
Daily retail revenue is driven by weekday effects, seasonality, festival
spikes and a slow growth trend, and the relationship between those drivers is
non linear and interactive (a Saturday in the Diwali window behaves very
differently from an ordinary Saturday). Gradient boosted trees model those
interactions directly from tabular lag and calendar features without requiring
stationarity, and they train in seconds on two years of daily data.

Ridge regression is trained alongside as a transparent linear reference; the
model that wins on validation MAE is the one that gets persisted.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from app.ml.evaluation import Metrics, baseline_metrics, best_baseline, evaluate, improvement_over

logger = logging.getLogger(__name__)

TARGET = "revenue"

# Only ~700 daily observations are available, so capacity is kept deliberately
# low. Deep, high capacity boosting memorised the training window and scored
# worse than a moving average on held out data; shallow trees with strong
# regularisation generalise far better on this sample size.
XGB_PARAMS: Dict[str, Any] = {
    "n_estimators": 120,
    "learning_rate": 0.06,
    "max_depth": 2,
    "min_child_weight": 10,
    "subsample": 0.8,
    "colsample_bytree": 0.6,
    "reg_lambda": 5.0,
    "reg_alpha": 0.5,
    "objective": "reg:squarederror",
    "random_state": 42,
    "n_jobs": 4,
}


def build_candidates() -> Dict[str, Any]:
    """Candidate estimators evaluated on the validation window."""
    return {
        "xgboost": XGBRegressor(**XGB_PARAMS),
        "ridge": Pipeline(
            [("scaler", StandardScaler()), ("model", Ridge(alpha=50.0, random_state=42))]
        ),
    }


def train_sales_model(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    feature_columns: List[str],
) -> Tuple[Any, str, Dict[str, Any]]:
    """Fit candidates, select on validation, report honestly on test."""
    x_train = train[feature_columns]
    y_train = train[TARGET]
    x_validation = validation[feature_columns]
    y_validation = validation[TARGET]
    x_test = test[feature_columns]
    y_test = test[TARGET]

    candidate_scores: Dict[str, Dict[str, Any]] = {}
    fitted: Dict[str, Any] = {}

    for name, estimator in build_candidates().items():
        estimator.fit(x_train, y_train)
        predictions = np.clip(estimator.predict(x_validation), 0, None)
        metrics = evaluate(y_validation.to_numpy(), predictions)
        candidate_scores[name] = metrics.to_dict()
        fitted[name] = estimator
        logger.info(
            "sales candidate %-8s validation MAE=%.2f RMSE=%.2f R2=%s",
            name,
            metrics.mae,
            metrics.rmse,
            metrics.r2,
        )

    selected_name = min(candidate_scores, key=lambda key: candidate_scores[key]["mae"])
    selected = fitted[selected_name]

    # Refit the winner on train + validation so it sees the most recent
    # information available before the held out test window.
    combined = pd.concat([train, validation], ignore_index=True)
    selected.fit(combined[feature_columns], combined[TARGET])

    test_predictions = np.clip(selected.predict(x_test), 0, None)
    test_metrics = evaluate(y_test.to_numpy(), test_predictions)

    baselines = baseline_metrics(test, TARGET)
    baseline_name, baseline_values = best_baseline(baselines)

    report: Dict[str, Any] = {
        "selected_algorithm": selected_name,
        "candidates_validation": candidate_scores,
        "test_metrics": test_metrics.to_dict(),
        "baselines_test": baselines,
        "best_baseline": baseline_name,
        "improvement_over_best_baseline": improvement_over(test_metrics, baseline_values),
        "train_rows": int(len(train)),
        "validation_rows": int(len(validation)),
        "test_rows": int(len(test)),
        "train_period": [str(train["date"].min().date()), str(train["date"].max().date())],
        "test_period": [str(test["date"].min().date()), str(test["date"].max().date())],
        "feature_count": len(feature_columns),
    }

    if hasattr(selected, "feature_importances_"):
        importances = sorted(
            zip(feature_columns, selected.feature_importances_),
            key=lambda pair: pair[1],
            reverse=True,
        )[:15]
        report["top_features"] = [
            {"feature": name, "importance": round(float(value), 5)}
            for name, value in importances
        ]

    logger.info(
        "sales model %s -> test MAE=%.2f (best baseline %s MAE=%.2f)",
        selected_name,
        test_metrics.mae,
        baseline_name,
        baseline_values.get("mae", float("nan")),
    )
    return selected, selected_name, report


def forecast_future(
    model: Any,
    history: pd.DataFrame,
    feature_columns: List[str],
    horizon_days: int,
    feature_builder,
) -> pd.DataFrame:
    """Recursive multi step forecast.

    Each predicted day is appended to the history so the next day's lag
    features are populated exactly as they would be in production.
    """
    working = history.copy()
    results: List[Dict[str, Any]] = []

    for _ in range(horizon_days):
        next_date = working["date"].max() + pd.Timedelta(days=1)
        placeholder = pd.DataFrame(
            [
                {
                    "date": next_date,
                    "revenue": np.nan,
                    "transactions": working["transactions"].tail(7).mean(),
                    "units": working["units"].tail(7).mean(),
                    "discount": working["discount"].tail(7).mean(),
                }
            ]
        )
        extended = pd.concat([working, placeholder], ignore_index=True)
        featured = feature_builder(extended)

        row = featured.tail(1)
        prediction = float(np.clip(model.predict(row[feature_columns])[0], 0, None))

        results.append({"date": next_date, "predicted_revenue": round(prediction, 2)})
        placeholder.loc[0, "revenue"] = prediction
        working = pd.concat([working, placeholder], ignore_index=True)

    return pd.DataFrame(results)
