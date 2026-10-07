"""Bridges the machine learning layer into business services.

Inventory intelligence works with or without trained models: when a model is
available its predictions are used, otherwise the service falls back to a
transparent statistical baseline. This keeps the platform functional on a
fresh installation and makes the ML contribution measurable.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.inventory_service import BulkDemandForecaster, DemandForecaster, InventoryService

logger = logging.getLogger(__name__)


def get_demand_forecaster(db: Session) -> Optional[DemandForecaster]:
    """Return a callable producing horizon demand for a product, if available."""
    try:
        from app.ml.predictor import PredictionService
    except Exception:  # pragma: no cover - ML layer not present yet
        return None

    service = PredictionService(db)
    if not service.demand_model_available():
        return None

    def _forecast(product_id: int, horizon_days: int) -> Tuple[float, str]:
        return service.demand_total(product_id, horizon_days)

    return _forecast


def get_bulk_demand_forecaster(db: Session) -> Optional[BulkDemandForecaster]:
    """Vectorised forecaster used when many products are scored at once."""
    try:
        from app.ml.predictor import PredictionService
    except Exception:  # pragma: no cover - ML layer not present yet
        return None

    service = PredictionService(db)
    if not service.demand_model_available():
        return None

    def _bulk(product_ids, horizon_days: int):
        return service.bulk_demand_totals(list(product_ids), horizon_days)

    return _bulk


def build_inventory_service(db: Session) -> InventoryService:
    """Construct an InventoryService wired to the best available forecaster."""
    return InventoryService(
        db,
        forecaster=get_demand_forecaster(db),
        bulk_forecaster=get_bulk_demand_forecaster(db),
    )
