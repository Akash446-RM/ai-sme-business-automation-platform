"""Alert endpoints."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession, require_manager
from app.core.pagination import Page, PageParams, page_params
from app.models.enums import AlertStatus
from app.models.user import User
from app.schemas.alert import AlertRead, AlertStatusUpdate, AlertSummary, ScanResult
from app.services.automation_service import AutomationService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=Page[AlertRead], summary="List alerts")
def list_alerts(
    db: DbSession,
    _: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    status: Optional[str] = Query(
        "open", pattern="^(open|acknowledged|resolved|dismissed|all)$"
    ),
    severity: Optional[str] = Query(None, pattern="^(critical|high|medium|low|info)$"),
    alert_type: Optional[str] = Query(None, max_length=30),
) -> Page[AlertRead]:
    alerts, total = AutomationService(db).list_alerts(
        params,
        status=None if status == "all" else status,
        severity=severity,
        alert_type=alert_type,
    )
    return Page.create([AlertRead.model_validate(alert) for alert in alerts], total, params)


@router.get("/summary", response_model=AlertSummary, summary="Open alert counts")
def summary(db: DbSession, _: CurrentUser) -> AlertSummary:
    return AutomationService(db).summary()


@router.post(
    "/scan",
    response_model=ScanResult,
    summary="Run the automation engine and refresh alerts",
)
def scan(
    db: DbSession,
    _: Annotated[User, Depends(require_manager)],
    horizon_days: int = Query(7, ge=1, le=90),
) -> ScanResult:
    return AutomationService(db).scan(horizon_days)


@router.patch("/{alert_id}", response_model=AlertRead, summary="Update alert status")
def update_status(
    alert_id: int, payload: AlertStatusUpdate, db: DbSession, _: CurrentUser
) -> AlertRead:
    return AlertRead.model_validate(
        AutomationService(db).update_status(alert_id, payload.status)
    )
