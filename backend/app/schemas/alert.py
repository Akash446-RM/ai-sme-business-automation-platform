"""Alert schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.schemas.common import ORMModel


class AlertRead(ORMModel):
    id: int
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    recommended_action: Optional[str]
    entity_type: Optional[str]
    entity_id: Optional[int]
    evidence: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


class AlertSummary(BaseModel):
    """Counts used by the dashboard badge and the alerts screen."""

    total_open: int
    critical: int
    high: int
    medium: int
    low: int
    by_type: Dict[str, int] = Field(default_factory=dict)


class ScanResult(BaseModel):
    """Outcome of an automation engine run."""

    scanned_at: datetime
    created: int
    updated: int
    auto_resolved: int
    total_open: int
    by_type: Dict[str, int] = Field(default_factory=dict)
    messages: List[str] = Field(default_factory=list)
