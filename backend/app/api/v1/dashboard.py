"""Dashboard endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.analytics import DashboardInsight, DashboardKpis, DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary, summary="Full dashboard payload")
def summary(db: DbSession, _: CurrentUser) -> DashboardSummary:
    return DashboardService(db).summary()


@router.get("/kpis", response_model=DashboardKpis, summary="Headline KPIs only")
def kpis(db: DbSession, _: CurrentUser) -> DashboardKpis:
    return DashboardService(db).kpis()


@router.get(
    "/insights",
    response_model=List[DashboardInsight],
    summary="Data derived business insights",
)
def insights(
    db: DbSession, _: CurrentUser, limit: int = Query(6, ge=1, le=20)
) -> List[DashboardInsight]:
    return DashboardService(db).insights(limit)
