"""Aggregates every version 1 API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    alerts,
    analytics,
    auth,
    customers,
    dashboard,
    employees,
    forecasting,
    inventory,
    products,
    reports,
    sales,
)

api_router = APIRouter()


@api_router.get("/status", tags=["meta"], summary="API status")
def api_status() -> dict:
    """Simple readiness probe for the versioned API surface."""
    return {"api": "v1", "status": "ok"}


api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(customers.router)
api_router.include_router(employees.router)
api_router.include_router(sales.router)
api_router.include_router(inventory.router)
api_router.include_router(analytics.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(forecasting.router)
api_router.include_router(alerts.router)
api_router.include_router(ai.router)
