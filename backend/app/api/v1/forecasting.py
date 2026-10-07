"""Forecasting endpoints."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession, require_manager
from app.ml.predictor import PredictionService
from app.ml.registry import ModelRegistry
from app.models.user import User
from app.schemas.common import Message

router = APIRouter(prefix="/forecasting", tags=["forecasting"])


@router.get("/status", summary="Which models are trained, and how good are they?")
def status(_: CurrentUser) -> Dict[str, Any]:
    payload = ModelRegistry.status()
    payload["metrics_report"] = ModelRegistry.read_metrics()
    return payload


@router.get("/sales", summary="Forecast total revenue for the coming days")
def sales_forecast(
    db: DbSession, _: CurrentUser, horizon_days: int = Query(7, ge=1, le=90)
) -> Dict[str, Any]:
    return PredictionService(db).forecast_sales(horizon_days)


@router.get("/demand/{product_id}", summary="Forecast demand for one product")
def demand_forecast(
    product_id: int,
    db: DbSession,
    _: CurrentUser,
    horizon_days: int = Query(7, ge=1, le=90),
) -> Dict[str, Any]:
    return PredictionService(db).forecast_demand(product_id, horizon_days)


@router.get(
    "/demand-summary",
    summary="Predicted demand versus available stock for at risk products",
)
def demand_summary(
    db: DbSession,
    _: CurrentUser,
    horizon_days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Combines forecasts with stock so the risk is immediately visible."""
    from app.services.forecast_service import build_inventory_service

    recommendations = build_inventory_service(db).reorder_recommendations(
        horizon_days=horizon_days, limit=limit
    )
    return {
        "horizon_days": horizon_days,
        "at_risk_count": sum(
            1 for item in recommendations if item.urgency in {"critical", "high"}
        ),
        "items": [
            {
                "product_id": item.product_id,
                "name": item.name,
                "sku": item.sku,
                "current_stock": item.current_stock,
                "forecast_demand": item.forecast_demand,
                "forecast_source": item.forecast_source,
                "recommended_quantity": item.recommended_quantity,
                "urgency": item.urgency,
                "days_of_cover": item.days_of_cover,
            }
            for item in recommendations
        ],
    }


@router.post(
    "/refresh-cache",
    response_model=Message,
    summary="Reload model artifacts and clear cached predictions",
)
def refresh_cache(_: Annotated[User, Depends(require_manager)]) -> Message:
    PredictionService.clear_cache()
    return Message(message="Model cache cleared. Fresh artifacts will be loaded on demand.")
