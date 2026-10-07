"""Inventory intelligence schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import MovementClass, StockStatus, TransactionType
from app.schemas.common import ORMModel


class InventoryTransactionRead(ORMModel):
    id: int
    product_id: int
    transaction_type: TransactionType
    quantity: int
    previous_stock: int
    new_stock: int
    reference: Optional[str]
    notes: Optional[str]
    created_at: datetime


class InventoryTransactionDetail(InventoryTransactionRead):
    product_name: Optional[str] = None
    product_sku: Optional[str] = None


class InventoryOverview(BaseModel):
    """Portfolio level view of stock health."""

    total_products: int
    total_units: int
    total_stock_value: Decimal
    healthy_count: int
    low_stock_count: int
    out_of_stock_count: int
    overstock_count: int
    dead_stock_count: int


class StockItem(BaseModel):
    """A product with its derived inventory status."""

    product_id: int
    name: str
    sku: str
    category: str
    stock: int
    reorder_level: int
    stock_status: StockStatus
    stock_value: Decimal
    units_sold_30d: int
    daily_velocity: float
    days_of_cover: Optional[float] = Field(
        default=None, description="Days of stock remaining at the current sales rate"
    )
    last_sold_at: Optional[datetime] = None
    movement_class: MovementClass


class ReorderRecommendation(BaseModel):
    """An explainable restocking recommendation.

    ``reasons`` and ``evidence`` are the exact facts the AI layer quotes when a
    user asks why a product should be reordered, which keeps AI explanations
    grounded in real data.
    """

    product_id: int
    name: str
    sku: str
    category: str
    current_stock: int
    reorder_level: int
    daily_velocity: float
    forecast_horizon_days: int
    forecast_demand: float
    safety_stock: float
    recommended_quantity: int
    urgency: str
    stock_status: StockStatus
    days_of_cover: Optional[float]
    estimated_cost: Decimal
    forecast_source: str = Field(
        description="Whether the demand figure came from the ML model or a statistical fallback"
    )
    reasons: List[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


class MovementItem(BaseModel):
    product_id: int
    name: str
    category: str
    stock: int
    units_sold: int
    revenue: Decimal


class MovementAnalysis(BaseModel):
    window_days: int
    fast_moving: List[MovementItem]
    slow_moving: List[MovementItem]
    never_sold: List[MovementItem]


class InventoryValuation(BaseModel):
    category: str
    product_count: int
    total_units: int
    cost_value: Decimal
    retail_value: Decimal
    potential_margin: Decimal
