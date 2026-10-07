"""Prediction service.

Loads persisted artifacts and serves forecasts. Predictions are cached briefly
because the underlying history only changes when new sales are recorded, and a
recursive multi step forecast is comparatively expensive.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ModelNotTrainedError, NotFoundError
from app.ml.dataset import load_daily_product_demand, load_daily_sales
from app.ml.features import build_demand_features, build_sales_features
from app.ml.registry import ModelRegistry
from app.repositories.product_repository import ProductRepository

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300
MAX_HORIZON_DAYS = 90


class _TtlCache:
    """Minimal thread safe time to live cache."""

    def __init__(self, ttl: int = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if time.time() - stored_at > self._ttl:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_cache = _TtlCache()


class PredictionService:
    """Serves forecasts from persisted models. Never trains."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.product_repo = ProductRepository(db)

    # -- availability -----------------------------------------------------
    @staticmethod
    def sales_model_available() -> bool:
        return ModelRegistry.sales_model() is not None

    @staticmethod
    def demand_model_available() -> bool:
        return ModelRegistry.demand_model() is not None

    @staticmethod
    def status() -> Dict[str, Any]:
        return ModelRegistry.status()

    # -- sales forecasting ------------------------------------------------
    def forecast_sales(self, horizon_days: int = 7) -> Dict[str, Any]:
        """Forecast total daily revenue for the coming days."""
        horizon_days = min(max(horizon_days, 1), MAX_HORIZON_DAYS)
        cache_key = f"sales:{horizon_days}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        artifact = ModelRegistry.sales_model()
        if artifact is None:
            raise ModelNotTrainedError(
                "The sales forecasting model has not been trained yet. "
                "Run: python -m app.scripts.train_models"
            )

        history = load_daily_sales(self.db)
        if history.empty:
            raise ModelNotTrainedError("There is no sales history to forecast from.")

        from app.ml.sales_model import forecast_future

        def builder(frame: pd.DataFrame) -> pd.DataFrame:
            featured, _ = build_sales_features(frame)
            return featured

        predictions = forecast_future(
            artifact.model, history, artifact.feature_columns, horizon_days, builder
        )

        recent = history.tail(30)
        recent_average = float(recent["revenue"].mean()) if len(recent) else 0.0
        total_predicted = float(predictions["predicted_revenue"].sum())

        # Uncertainty band derived from the model's own held out test error.
        mae = float(artifact.metrics.get("test_metrics", {}).get("mae", 0) or 0)

        result = {
            "horizon_days": horizon_days,
            "generated_at": datetime.now().isoformat(),
            "model": {
                "algorithm": artifact.algorithm,
                "trained_at": artifact.trained_at.isoformat(),
                "test_mae": mae,
                "test_mape": artifact.metrics.get("test_metrics", {}).get("mape"),
            },
            "predictions": [
                {
                    "date": row["date"].date().isoformat(),
                    "predicted_revenue": float(row["predicted_revenue"]),
                    "lower_bound": round(max(float(row["predicted_revenue"]) - mae, 0), 2),
                    "upper_bound": round(float(row["predicted_revenue"]) + mae, 2),
                }
                for _, row in predictions.iterrows()
            ],
            "total_predicted_revenue": round(total_predicted, 2),
            "daily_average_predicted": round(total_predicted / horizon_days, 2),
            "recent_daily_average": round(recent_average, 2),
            "change_vs_recent_percent": (
                round((total_predicted / horizon_days - recent_average) / recent_average * 100, 2)
                if recent_average > 0
                else None
            ),
            "history": [
                {
                    "date": row["date"].date().isoformat(),
                    "revenue": round(float(row["revenue"]), 2),
                }
                for _, row in history.tail(60).iterrows()
            ],
        }
        _cache.set(cache_key, result)
        return result

    # -- demand forecasting -----------------------------------------------
    def _demand_frame(self) -> pd.DataFrame:
        cached = _cache.get("demand_frame")
        if cached is not None:
            return cached
        frame = load_daily_product_demand(self.db)
        _cache.set("demand_frame", frame)
        return frame

    def forecast_demand(self, product_id: int, horizon_days: int = 7) -> Dict[str, Any]:
        """Forecast daily demand for one product."""
        horizon_days = min(max(horizon_days, 1), MAX_HORIZON_DAYS)
        cache_key = f"demand:{product_id}:{horizon_days}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        product = self.product_repo.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")

        artifact = ModelRegistry.demand_model()
        if artifact is None:
            raise ModelNotTrainedError(
                "The demand forecasting model has not been trained yet. "
                "Run: python -m app.scripts.train_models"
            )

        frame = self._demand_frame()
        history = frame[frame["product_id"] == product_id].sort_values("date")
        if history.empty:
            raise ModelNotTrainedError(
                f"'{product.name}' does not have enough sales history for a model "
                f"based forecast. Recommendations will use recent sales velocity instead.",
                {"product_id": product_id},
            )

        from app.ml.demand_model import forecast_product

        def builder(working: pd.DataFrame) -> pd.DataFrame:
            featured, _ = build_demand_features(working)
            return featured

        predictions = forecast_product(
            artifact.model, history, artifact.feature_columns, horizon_days, builder
        )
        if predictions.empty:
            raise ModelNotTrainedError(
                f"Could not build a forecast for '{product.name}' from its history."
            )

        total = float(predictions["predicted_units"].sum())
        recent_daily = float(history.tail(30)["units"].mean()) if len(history) else 0.0
        mae = float(artifact.metrics.get("test_metrics", {}).get("mae", 0) or 0)

        result = {
            "product_id": product_id,
            "product_name": product.name,
            "sku": product.sku,
            "category": product.category,
            "current_stock": product.stock,
            "horizon_days": horizon_days,
            "generated_at": datetime.now().isoformat(),
            "model": {
                "algorithm": artifact.algorithm,
                "trained_at": artifact.trained_at.isoformat(),
                "test_mae_units_per_day": mae,
            },
            "predictions": [
                {
                    "date": row["date"].date().isoformat(),
                    "predicted_units": float(row["predicted_units"]),
                }
                for _, row in predictions.iterrows()
            ],
            "total_predicted_units": round(total, 2),
            "daily_average_predicted": round(total / horizon_days, 3),
            "recent_daily_average": round(recent_daily, 3),
            "expected_stock_after_horizon": round(product.stock - total, 1),
            "stockout_expected": total > product.stock,
            "history": [
                {
                    "date": row["date"].date().isoformat(),
                    "units": int(row["units"]),
                }
                for _, row in history.tail(60).iterrows()
            ],
        }
        _cache.set(cache_key, result)
        return result

    def demand_total(self, product_id: int, horizon_days: int = 7) -> Tuple[float, str]:
        """Total predicted demand over a horizon, for the inventory engine.

        Falls back to recent velocity when the product is not modelled, so
        recommendations always work.
        """
        try:
            forecast = self.forecast_demand(product_id, horizon_days)
            return float(forecast["total_predicted_units"]), "ml_demand_model"
        except (ModelNotTrainedError, NotFoundError):
            return self._velocity_fallback(product_id, horizon_days)

    def _velocity_fallback(self, product_id: int, horizon_days: int) -> Tuple[float, str]:
        from app.repositories.inventory_repository import InventoryRepository

        since = datetime.now() - timedelta(days=30)
        units = InventoryRepository(self.db).units_sold(product_id, since=since)
        return (units / 30.0) * horizon_days, "statistical_baseline"

    def bulk_demand_totals(
        self, product_ids: List[int], horizon_days: int = 7
    ) -> Dict[int, Tuple[float, str]]:
        """Horizon demand for many products in a single vectorised pass.

        Forecasting products one at a time rebuilds the whole feature matrix per
        product per step, which is far too slow for a 70 product reorder run.
        Here every product advances through the horizon together: one feature
        build and one ``predict`` call per step for the entire batch.
        """
        if not product_ids:
            return {}

        requested = list(dict.fromkeys(int(pid) for pid in product_ids))
        cache_key = f"bulk:{horizon_days}:{hash(tuple(sorted(requested)))}"
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        artifact = ModelRegistry.demand_model()
        if artifact is None:
            result = {
                pid: self._velocity_fallback(pid, horizon_days) for pid in requested
            }
            _cache.set(cache_key, result)
            return result

        frame = self._demand_frame()
        modelled = set(frame["product_id"].unique().tolist()) & set(requested)
        results: Dict[int, Tuple[float, str]] = {
            pid: self._velocity_fallback(pid, horizon_days)
            for pid in requested
            if pid not in modelled
        }

        if modelled:
            working = frame[frame["product_id"].isin(modelled)].copy()
            totals: Dict[int, float] = {pid: 0.0 for pid in modelled}
            static_columns = [
                "product_id",
                "category",
                "selling_price",
                "cost_price",
                "avg_price",
            ]
            last_rows = (
                working.sort_values("date").groupby("product_id").tail(1)
            )[static_columns].reset_index(drop=True)

            for _ in range(horizon_days):
                next_date = working["date"].max() + pd.Timedelta(days=1)
                placeholder = last_rows.copy()
                placeholder["date"] = next_date
                placeholder["units"] = np.nan
                placeholder["revenue"] = 0.0

                extended = pd.concat([working, placeholder], ignore_index=True)
                featured, _ = build_demand_features(extended)
                step = featured[featured["date"] == next_date]
                if step.empty:
                    break

                predictions = np.clip(
                    artifact.model.predict(step[artifact.feature_columns]), 0, None
                )
                predicted = dict(zip(step["product_id"].astype(int), predictions))

                placeholder["units"] = (
                    placeholder["product_id"].astype(int).map(predicted).fillna(0.0)
                )
                for pid, value in predicted.items():
                    totals[pid] = totals.get(pid, 0.0) + float(value)
                working = pd.concat([working, placeholder], ignore_index=True)

            for pid in modelled:
                results[int(pid)] = (round(totals.get(pid, 0.0), 2), "ml_demand_model")

        _cache.set(cache_key, results)
        return results

    @staticmethod
    def clear_cache() -> None:
        _cache.clear()
        ModelRegistry.invalidate()
