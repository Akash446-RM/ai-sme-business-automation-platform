"""Automation engine.

Scans the business for situations that deserve attention and records them as
alerts. Each detector states the condition it checks, the evidence behind it
and the action it recommends, so an alert is always actionable and auditable.

Alerts are deduplicated by a stable key: re-running the scan refreshes an
existing open alert instead of flooding the list with copies. Conditions that
have resolved themselves are closed automatically.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models.alert import Alert
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.schemas.alert import AlertSummary, ScanResult
from app.services.analytics_service import AnalyticsService
from app.services.forecast_service import build_inventory_service

logger = logging.getLogger(__name__)

SALES_TREND_WINDOW_DAYS = 14
DEMAND_SHIFT_WINDOW_DAYS = 30
DEMAND_SHIFT_THRESHOLD = 35.0
MAX_STOCK_ALERTS = 40


class AutomationService:
    """Detects business conditions and maintains the alert list."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.analytics = AnalyticsService(db)
        self.inventory = build_inventory_service(db)

    # -- alert persistence -------------------------------------------------
    def _upsert(
        self,
        *,
        dedupe_key: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        description: str,
        recommended_action: Optional[str],
        entity_type: Optional[str],
        entity_id: Optional[int],
        evidence: Dict[str, Any],
    ) -> str:
        """Create the alert, or refresh it if it already exists."""
        existing = self.db.execute(
            select(Alert).where(Alert.dedupe_key == dedupe_key)
        ).scalar_one_or_none()

        if existing is None:
            self.db.add(
                Alert(
                    dedupe_key=dedupe_key,
                    alert_type=alert_type,
                    severity=severity,
                    status=AlertStatus.OPEN,
                    title=title,
                    description=description,
                    recommended_action=recommended_action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    evidence=evidence,
                )
            )
            return "created"

        existing.severity = severity
        existing.title = title
        existing.description = description
        existing.recommended_action = recommended_action
        existing.evidence = evidence
        # A dismissed alert stays dismissed; a resolved one reopens if it recurs.
        if existing.status == AlertStatus.RESOLVED:
            existing.status = AlertStatus.OPEN
            existing.resolved_at = None
        return "updated"

    def _auto_resolve(self, active_keys: set[str]) -> int:
        """Close open alerts whose triggering condition no longer holds."""
        open_alerts = list(
            self.db.execute(
                select(Alert).where(Alert.status == AlertStatus.OPEN)
            ).scalars()
        )
        resolved = 0
        for alert in open_alerts:
            if alert.dedupe_key not in active_keys:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                resolved += 1
        return resolved

    # -- the scan ----------------------------------------------------------
    def scan(self, horizon_days: int = 7) -> ScanResult:
        """Run every detector and reconcile the alert list."""
        messages: List[str] = []
        counters = Counter({"created": 0, "updated": 0})
        active_keys: set[str] = set()
        by_type: Counter = Counter()

        detectors = (
            self._detect_stock_conditions,
            self._detect_demand_shifts,
            self._detect_sales_trend,
            self._detect_dead_stock,
        )
        for detector in detectors:
            try:
                outcomes = detector(horizon_days)
            except Exception as exc:  # pragma: no cover - a detector must never break the scan
                logger.exception("Detector %s failed", detector.__name__)
                messages.append(f"{detector.__name__} failed: {exc}")
                continue

            for key, alert_type, action in outcomes:
                active_keys.add(key)
                counters[action] += 1
                by_type[str(alert_type)] += 1

        auto_resolved = self._auto_resolve(active_keys)
        self.db.commit()

        total_open = int(
            self.db.execute(
                select(func.count(Alert.id)).where(Alert.status == AlertStatus.OPEN)
            ).scalar_one()
        )
        logger.info(
            "Automation scan: %s created, %s updated, %s auto resolved, %s open",
            counters["created"],
            counters["updated"],
            auto_resolved,
            total_open,
        )
        return ScanResult(
            scanned_at=datetime.now(),
            created=counters["created"],
            updated=counters["updated"],
            auto_resolved=auto_resolved,
            total_open=total_open,
            by_type=dict(by_type),
            messages=messages,
        )

    # -- detectors ---------------------------------------------------------
    def _detect_stock_conditions(
        self, horizon_days: int
    ) -> List[Tuple[str, AlertType, str]]:
        """Out of stock, low stock and forecast driven stockout risk.

        The three conditions are mutually exclusive per product so the owner
        sees one clear alert rather than three overlapping ones.
        """
        outcomes: List[Tuple[str, AlertType, str]] = []
        # Include non actionable results too: a product sitting below its
        # reorder level is still worth reporting even when the forecast says
        # current cover is adequate, because the reorder level is the owner's
        # own policy threshold.
        recommendations = self.inventory.reorder_recommendations(
            horizon_days=horizon_days, limit=MAX_STOCK_ALERTS, only_actionable=False
        )

        for item in recommendations:
            below_policy = item.current_stock <= item.reorder_level
            if item.recommended_quantity <= 0 and not below_policy:
                continue
            # Ignore noise: a product with no recent movement and a token
            # one unit suggestion is not worth an owner's attention.
            if (
                item.recommended_quantity <= 1
                and item.daily_velocity <= 0
                and item.current_stock > 0
            ):
                continue

            evidence = {
                **item.evidence,
                "recommended_quantity": item.recommended_quantity,
                "estimated_cost": float(item.estimated_cost),
                "forecast_source": item.forecast_source,
                "reasons": item.reasons,
            }
            action = (
                f"Reorder approximately {item.recommended_quantity} units "
                f"(estimated cost {float(item.estimated_cost):,.0f})."
                if item.recommended_quantity > 0
                else (
                    "Stock is below your reorder level. Current cover is adequate, "
                    "so review whether the reorder level is still appropriate."
                )
            )

            if item.current_stock <= 0:
                alert_type = AlertType.OUT_OF_STOCK
                # A product with no stock but no measurable demand is a stale
                # listing, not an emergency. Severity follows real demand.
                has_demand = item.forecast_demand >= 1 or item.daily_velocity > 0
                severity = AlertSeverity.CRITICAL if has_demand else AlertSeverity.LOW
                title = f"Out of stock: {item.name}"
                if has_demand:
                    description = (
                        f"{item.name} ({item.sku}) has no stock available. "
                        f"Expected demand over the next {horizon_days} days is "
                        f"{item.forecast_demand:.0f} units, so sales are being lost now."
                    )
                else:
                    description = (
                        f"{item.name} ({item.sku}) has no stock available. It has not sold "
                        f"recently, so no immediate revenue is being lost, but the listing "
                        f"cannot be fulfilled if a customer asks for it."
                    )
            elif item.forecast_demand > item.current_stock:
                alert_type = AlertType.STOCKOUT_RISK
                severity = (
                    AlertSeverity.CRITICAL if item.urgency == "critical" else AlertSeverity.HIGH
                )
                cover = (
                    f"about {item.days_of_cover:.1f} days"
                    if item.days_of_cover is not None
                    else "an unknown number of days"
                )
                title = f"Potential stockout: {item.name}"
                description = (
                    f"{item.name} has {item.current_stock} units in stock but forecast "
                    f"demand over the next {horizon_days} days is "
                    f"{item.forecast_demand:.0f} units. At the current sales rate stock "
                    f"will last {cover}."
                )
            else:
                alert_type = AlertType.LOW_STOCK
                severity = (
                    AlertSeverity.HIGH if item.urgency == "high" else AlertSeverity.MEDIUM
                )
                title = f"Low stock: {item.name}"
                description = (
                    f"{item.name} has fallen to {item.current_stock} units, at or below "
                    f"its reorder level of {item.reorder_level}."
                )

            key = f"stock:{item.product_id}:{alert_type}"
            outcomes.append(
                (
                    key,
                    alert_type,
                    self._upsert(
                        dedupe_key=key,
                        alert_type=alert_type,
                        severity=severity,
                        title=title,
                        description=description,
                        recommended_action=action,
                        entity_type="product",
                        entity_id=item.product_id,
                        evidence=evidence,
                    ),
                )
            )
        return outcomes

    def _detect_demand_shifts(self, _: int) -> List[Tuple[str, AlertType, str]]:
        """Products whose demand has moved sharply in either direction."""
        outcomes: List[Tuple[str, AlertType, str]] = []
        shifts = self.analytics.product_demand_shifts(
            window_days=DEMAND_SHIFT_WINDOW_DAYS,
            threshold_percent=DEMAND_SHIFT_THRESHOLD,
            limit=8,
        )

        for entry in shifts["rising_demand"]:
            key = f"demand_surge:{entry['product_id']}"
            outcomes.append(
                (
                    key,
                    AlertType.DEMAND_SURGE,
                    self._upsert(
                        dedupe_key=key,
                        alert_type=AlertType.DEMAND_SURGE,
                        severity=AlertSeverity.MEDIUM,
                        title=f"Demand rising: {entry['name']}",
                        description=(
                            f"{entry['name']} sold {entry['current_units']} units in the last "
                            f"{DEMAND_SHIFT_WINDOW_DAYS} days versus {entry['previous_units']} "
                            f"in the previous {DEMAND_SHIFT_WINDOW_DAYS} days, a change of "
                            f"{entry['change_percent']:.0f}%. Current stock is "
                            f"{entry['current_stock']} units."
                        ),
                        recommended_action=(
                            "Review the reorder level and stock cover for this product so the "
                            "higher demand can be met."
                        ),
                        entity_type="product",
                        entity_id=entry["product_id"],
                        evidence=entry,
                    ),
                )
            )

        for entry in shifts["falling_demand"]:
            key = f"demand_drop:{entry['product_id']}"
            outcomes.append(
                (
                    key,
                    AlertType.DEMAND_DROP,
                    self._upsert(
                        dedupe_key=key,
                        alert_type=AlertType.DEMAND_DROP,
                        severity=AlertSeverity.LOW,
                        title=f"Demand falling: {entry['name']}",
                        description=(
                            f"{entry['name']} sold {entry['current_units']} units in the last "
                            f"{DEMAND_SHIFT_WINDOW_DAYS} days versus {entry['previous_units']} "
                            f"previously, a change of {entry['change_percent']:.0f}%. "
                            f"{entry['current_stock']} units are still in stock."
                        ),
                        recommended_action=(
                            "Avoid over ordering. Consider a promotion to clear existing stock."
                        ),
                        entity_type="product",
                        entity_id=entry["product_id"],
                        evidence=entry,
                    ),
                )
            )
        return outcomes

    def _detect_sales_trend(self, _: int) -> List[Tuple[str, AlertType, str]]:
        """Overall revenue growth or decline versus the previous period."""
        trend = self.analytics.detect_sales_trend(window_days=SALES_TREND_WINDOW_DAYS)
        change = trend["revenue_change_percent"]
        if change is None or trend["direction"] == "stable":
            return []

        growing = trend["direction"] == "growing"
        alert_type = AlertType.SALES_GROWTH if growing else AlertType.SALES_DECLINE
        key = f"sales_trend:{alert_type}"

        current = trend["current_period"]["revenue"]
        previous = trend["previous_period"]["revenue"]
        evidence = {
            "window_days": SALES_TREND_WINDOW_DAYS,
            "current_revenue": round(current, 2),
            "previous_revenue": round(previous, 2),
            "change_percent": change,
            "current_transactions": trend["current_period"]["transactions"],
            "previous_transactions": trend["previous_period"]["transactions"],
        }

        return [
            (
                key,
                alert_type,
                self._upsert(
                    dedupe_key=key,
                    alert_type=alert_type,
                    severity=AlertSeverity.INFO if growing else AlertSeverity.HIGH,
                    title=(
                        "Revenue is growing" if growing else "Revenue is declining"
                    ),
                    description=(
                        f"Revenue over the last {SALES_TREND_WINDOW_DAYS} days was "
                        f"{current:,.0f} compared with {previous:,.0f} in the previous "
                        f"{SALES_TREND_WINDOW_DAYS} days, a change of {change:.1f}%."
                    ),
                    recommended_action=(
                        "Keep fast moving products in stock to sustain the growth."
                        if growing
                        else "Check stock availability, pricing and customer follow ups."
                    ),
                    entity_type="business",
                    entity_id=None,
                    evidence=evidence,
                ),
            )
        ]

    def _detect_dead_stock(self, _: int) -> List[Tuple[str, AlertType, str]]:
        """Capital tied up in products that have not sold in 90 days."""
        dead = self.inventory.dead_stock(limit=5)
        outcomes: List[Tuple[str, AlertType, str]] = []
        for item in dead:
            if item.stock_value <= 0:
                continue
            key = f"dead_stock:{item.product_id}"
            outcomes.append(
                (
                    key,
                    AlertType.DEAD_STOCK,
                    self._upsert(
                        dedupe_key=key,
                        alert_type=AlertType.DEAD_STOCK,
                        severity=AlertSeverity.LOW,
                        title=f"Dead stock: {item.name}",
                        description=(
                            f"{item.name} has {item.stock} units worth "
                            f"{float(item.stock_value):,.0f} and has not sold in 90 days."
                        ),
                        recommended_action=(
                            "Consider a discount, a bundle or returning the stock to the supplier."
                        ),
                        entity_type="product",
                        entity_id=item.product_id,
                        evidence={
                            "stock": item.stock,
                            "stock_value": float(item.stock_value),
                            "category": item.category,
                        },
                    ),
                )
            )
        return outcomes

    # -- queries -----------------------------------------------------------
    def list_alerts(
        self,
        params: PageParams,
        *,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> Tuple[List[Alert], int]:
        statement = select(Alert)
        if status:
            statement = statement.where(Alert.status == status)
        if severity:
            statement = statement.where(Alert.severity == severity)
        if alert_type:
            statement = statement.where(Alert.alert_type == alert_type)

        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 3,
            AlertSeverity.INFO: 4,
        }
        ordering = func.field if False else None  # keep dialect neutral
        statement = statement.order_by(Alert.created_at.desc(), Alert.id.desc())

        total = int(
            self.db.execute(
                select(func.count()).select_from(statement.order_by(None).subquery())
            ).scalar_one()
        )
        rows = list(
            self.db.execute(statement.offset(params.offset).limit(params.limit)).scalars()
        )
        rows.sort(key=lambda alert: severity_order.get(alert.severity, 5))
        return rows, total

    def summary(self) -> AlertSummary:
        rows = self.db.execute(
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.status == AlertStatus.OPEN)
            .group_by(Alert.severity)
        ).all()
        counts = {str(row[0]): int(row[1]) for row in rows}

        type_rows = self.db.execute(
            select(Alert.alert_type, func.count(Alert.id))
            .where(Alert.status == AlertStatus.OPEN)
            .group_by(Alert.alert_type)
        ).all()

        return AlertSummary(
            total_open=sum(counts.values()),
            critical=counts.get(str(AlertSeverity.CRITICAL), 0),
            high=counts.get(str(AlertSeverity.HIGH), 0),
            medium=counts.get(str(AlertSeverity.MEDIUM), 0),
            low=counts.get(str(AlertSeverity.LOW), 0)
            + counts.get(str(AlertSeverity.INFO), 0),
            by_type={str(row[0]): int(row[1]) for row in type_rows},
        )

    def update_status(self, alert_id: int, status: AlertStatus) -> Alert:
        from app.core.exceptions import NotFoundError

        alert = self.db.get(Alert, alert_id)
        if alert is None:
            raise NotFoundError(f"Alert {alert_id} was not found.")
        alert.status = status
        alert.resolved_at = datetime.now() if status == AlertStatus.RESOLVED else None
        self.db.commit()
        self.db.refresh(alert)
        return alert
