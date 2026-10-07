"""Offline model training entry point.

This script is the only place where a model is fitted. The API never trains;
it loads the artifacts produced here.

Usage:
    python -m app.scripts.train_models                # train both models
    python -m app.scripts.train_models --only sales
    python -m app.scripts.train_models --test-days 45
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import Any, Dict

from app.core.database import SessionLocal, engine
from app.core.logging_config import configure_logging
from app.ml.dataset import (
    MIN_DAYS_FOR_TRAINING,
    load_daily_product_demand,
    load_daily_sales,
    validate_dataset,
)
from app.ml.demand_model import train_demand_model
from app.ml.features import (
    build_demand_features,
    build_sales_features,
    chronological_split,
)
from app.ml.registry import (
    DEMAND_MODEL_FILE,
    SALES_MODEL_FILE,
    ModelArtifact,
    ModelRegistry,
)
from app.ml.sales_model import train_sales_model

logger = logging.getLogger("train")


def train_sales(db, test_days: int, validation_days: int) -> Dict[str, Any]:
    print("\n--- Sales forecasting model ---")
    raw = load_daily_sales(db)
    validate_dataset(raw, name="daily_sales", min_rows=MIN_DAYS_FOR_TRAINING)

    frame, feature_columns = build_sales_features(raw)
    train, validation, test = chronological_split(
        frame, test_days=test_days, validation_days=validation_days
    )
    if len(train) < 30 or test.empty:
        raise ValueError(
            "Not enough history for a chronological split. "
            "Reduce --test-days or seed more sales data."
        )

    model, algorithm, report = train_sales_model(train, validation, test, feature_columns)

    artifact = ModelArtifact(
        model=model,
        feature_columns=feature_columns,
        target="revenue",
        algorithm=algorithm,
        trained_at=datetime.now(),
        metrics=report,
        extra={"history_days": int(len(raw))},
    )
    ModelRegistry.save(artifact, SALES_MODEL_FILE)

    test_metrics = report["test_metrics"]
    baseline = report["baselines_test"][report["best_baseline"]]
    print(f"  algorithm        : {algorithm}")
    print(f"  test MAE         : {test_metrics['mae']:,.2f}")
    print(f"  test RMSE        : {test_metrics['rmse']:,.2f}")
    print(f"  test MAPE        : {test_metrics['mape']}%")
    print(f"  test R2          : {test_metrics['r2']}")
    print(f"  best baseline    : {report['best_baseline']} (MAE {baseline['mae']:,.2f})")
    print(f"  improvement      : {report['improvement_over_best_baseline']}")
    return report


def train_demand(db, test_days: int, validation_days: int) -> Dict[str, Any]:
    print("\n--- Demand forecasting model ---")
    raw = load_daily_product_demand(db)
    validate_dataset(raw, name="daily_product_demand", min_rows=500)

    frame, feature_columns = build_demand_features(raw)
    train, validation, test = chronological_split(
        frame, test_days=test_days, validation_days=validation_days
    )
    if train.empty or test.empty:
        raise ValueError("Not enough product history for a chronological split.")

    model, algorithm, report = train_demand_model(train, validation, test, feature_columns)

    artifact = ModelArtifact(
        model=model,
        feature_columns=feature_columns,
        target="units",
        algorithm=algorithm,
        trained_at=datetime.now(),
        metrics=report,
        extra={
            "products_modelled": report["products_modelled"],
            "category_levels": sorted(raw["category"].unique().tolist()),
        },
    )
    ModelRegistry.save(artifact, DEMAND_MODEL_FILE)

    test_metrics = report["test_metrics"]
    baseline = report["baselines_test"][report["best_baseline"]]
    print(f"  algorithm        : {algorithm}")
    print(f"  products modelled: {report['products_modelled']}")
    print(f"  test MAE         : {test_metrics['mae']:.3f} units/day")
    print(f"  test RMSE        : {test_metrics['rmse']:.3f}")
    print(f"  test sMAPE       : {test_metrics['smape']}%")
    print(f"  best baseline    : {report['best_baseline']} (MAE {baseline['mae']:.3f})")
    print(f"  improvement      : {report['improvement_over_best_baseline']}")
    return report


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Train forecasting models")
    parser.add_argument("--only", choices=["sales", "demand"], default=None)
    parser.add_argument("--test-days", type=int, default=60)
    parser.add_argument("--validation-days", type=int, default=60)
    args = parser.parse_args()

    started = datetime.now()
    summary: Dict[str, Any] = {
        "trained_at": started.isoformat(),
        "test_days": args.test_days,
        "validation_days": args.validation_days,
    }

    with SessionLocal() as db:
        try:
            if args.only in (None, "sales"):
                summary["sales_forecast"] = train_sales(
                    db, args.test_days, args.validation_days
                )
            if args.only in (None, "demand"):
                summary["demand_forecast"] = train_demand(
                    db, args.test_days, args.validation_days
                )
        except ValueError as exc:
            print(f"\n[error] {exc}")
            return 1

    # Merge with any previously written metrics so a partial run keeps history.
    existing = ModelRegistry.read_metrics() or {}
    existing.update(summary)
    ModelRegistry.write_metrics(existing)
    ModelRegistry.invalidate()

    elapsed = (datetime.now() - started).total_seconds()
    print(f"\n[done] training finished in {elapsed:.1f}s")
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
