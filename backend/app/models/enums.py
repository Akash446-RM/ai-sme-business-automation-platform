"""Enumerations shared across the domain model."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String backed enum that serialises to its value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class UserRole(StrEnum):
    """Application roles used for authorisation."""

    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class TransactionType(StrEnum):
    """Reason a product's stock level changed."""

    SALE = "sale"
    PURCHASE = "purchase"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    INITIAL = "initial"
    DAMAGE = "damage"


class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    CREDIT = "credit"


class AlertType(StrEnum):
    """Categories emitted by the automation engine."""

    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    STOCKOUT_RISK = "stockout_risk"
    OVERSTOCK = "overstock"
    DEMAND_SURGE = "demand_surge"
    DEMAND_DROP = "demand_drop"
    SALES_GROWTH = "sales_growth"
    SALES_DECLINE = "sales_decline"
    DEAD_STOCK = "dead_stock"


class AlertSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class StockStatus(StrEnum):
    """Derived inventory health classification."""

    OUT_OF_STOCK = "out_of_stock"
    LOW = "low"
    HEALTHY = "healthy"
    OVERSTOCK = "overstock"


class MovementClass(StrEnum):
    """Sales velocity classification of a product."""

    FAST = "fast_moving"
    MEDIUM = "medium_moving"
    SLOW = "slow_moving"
    DEAD = "no_movement"
