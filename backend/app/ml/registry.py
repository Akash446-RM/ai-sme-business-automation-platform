"""Persistence and lazy loading of trained model artifacts.

Models are trained offline by ``app.scripts.train_models`` and only ever
loaded here. Nothing in the request path fits a model.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import joblib

from app.core.config import settings

logger = logging.getLogger(__name__)

SALES_MODEL_FILE = "sales_forecast.joblib"
DEMAND_MODEL_FILE = "demand_forecast.joblib"
METRICS_FILE = "metrics.json"


class ModelArtifact:
    """A trained estimator together with everything needed to reuse it."""

    def __init__(
        self,
        *,
        model: Any,
        feature_columns: list[str],
        target: str,
        algorithm: str,
        trained_at: datetime,
        metrics: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.model = model
        self.feature_columns = feature_columns
        self.target = target
        self.algorithm = algorithm
        self.trained_at = trained_at
        self.metrics = metrics
        self.extra = extra or {}

    def describe(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "target": self.target,
            "feature_count": len(self.feature_columns),
            "trained_at": self.trained_at.isoformat(),
            "metrics": self.metrics,
            **{key: value for key, value in self.extra.items() if key != "training_frame"},
        }


class ModelRegistry:
    """Process wide cache of loaded artifacts."""

    _lock = threading.Lock()
    _cache: Dict[str, Optional[ModelArtifact]] = {}

    @staticmethod
    def path(filename: str) -> Path:
        return settings.model_dir / filename

    @classmethod
    def save(cls, artifact: ModelArtifact, filename: str) -> Path:
        target = cls.path(filename)
        joblib.dump(artifact, target)
        with cls._lock:
            cls._cache[filename] = artifact
        logger.info("Saved model artifact to %s", target)
        return target

    @classmethod
    def load(cls, filename: str) -> Optional[ModelArtifact]:
        with cls._lock:
            if filename in cls._cache:
                return cls._cache[filename]

        target = cls.path(filename)
        if not target.exists():
            with cls._lock:
                cls._cache[filename] = None
            return None

        try:
            artifact = joblib.load(target)
        except Exception as exc:  # pragma: no cover - corrupted artifact
            logger.error("Could not load model artifact %s: %s", target, exc)
            artifact = None

        with cls._lock:
            cls._cache[filename] = artifact
        return artifact

    @classmethod
    def invalidate(cls) -> None:
        with cls._lock:
            cls._cache.clear()

    @classmethod
    def sales_model(cls) -> Optional[ModelArtifact]:
        return cls.load(SALES_MODEL_FILE)

    @classmethod
    def demand_model(cls) -> Optional[ModelArtifact]:
        return cls.load(DEMAND_MODEL_FILE)

    @classmethod
    def write_metrics(cls, payload: Dict[str, Any]) -> Path:
        target = cls.path(METRICS_FILE)
        target.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        logger.info("Wrote training metrics to %s", target)
        return target

    @classmethod
    def read_metrics(cls) -> Optional[Dict[str, Any]]:
        target = cls.path(METRICS_FILE)
        if not target.exists():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - defensive
            return None

    @classmethod
    def status(cls) -> Dict[str, Any]:
        sales = cls.sales_model()
        demand = cls.demand_model()
        return {
            "sales_model_trained": sales is not None,
            "demand_model_trained": demand is not None,
            "sales_model": sales.describe() if sales else None,
            "demand_model": demand.describe() if demand else None,
            "model_directory": str(settings.model_dir),
        }
