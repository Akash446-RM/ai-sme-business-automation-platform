"""Report schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.analytics import (
    CategoryPerformance,
    CustomerPerformance,
    EmployeeLeaderboardEntry,
    PaymentMix,
    ProductPerformance,
    TrendPoint,
)
from app.schemas.inventory import InventoryValuation, ReorderRecommendation, StockItem


class ReportMeta(BaseModel):
    """Provenance for every generated report."""

    report_type: str
    title: str
    date_from: date
    date_to: date
    generated_at: datetime
    filters: Dict[str, Any] = Field(default_factory=dict)


class SalesReport(BaseModel):
    meta: ReportMeta
    total_revenue: Decimal
    total_transactions: int
    total_units: int
    average_order_value: Decimal
    gross_profit: Decimal
    gross_margin_percent: float
    previous_revenue: Decimal
    revenue_growth_percent: Optional[float]
    daily_breakdown: List[TrendPoint]
    payment_mix: List[PaymentMix]


class RevenueReport(BaseModel):
    meta: ReportMeta
    monthly_breakdown: List[TrendPoint]
    category_breakdown: List[CategoryPerformance]
    total_revenue: Decimal
    total_gross_profit: Decimal
    best_month: Optional[TrendPoint] = None
    worst_month: Optional[TrendPoint] = None


class InventoryReport(BaseModel):
    meta: ReportMeta
    total_products: int
    total_units: int
    total_stock_value: Decimal
    low_stock_items: List[StockItem]
    out_of_stock_items: List[StockItem]
    dead_stock_items: List[StockItem]
    valuation_by_category: List[InventoryValuation]
    reorder_recommendations: List[ReorderRecommendation]


class ProductReport(BaseModel):
    meta: ReportMeta
    best_performers: List[ProductPerformance]
    worst_performers: List[ProductPerformance]
    category_performance: List[CategoryPerformance]


class CustomerReport(BaseModel):
    meta: ReportMeta
    top_customers: List[CustomerPerformance]
    total_active_customers: int
    repeat_customer_count: int
    repeat_rate_percent: float
    average_customer_value: Decimal


class BusinessSummaryReport(BaseModel):
    """One page overview combining every domain."""

    meta: ReportMeta
    revenue: Decimal
    gross_profit: Decimal
    gross_margin_percent: float
    transactions: int
    units_sold: int
    average_order_value: Decimal
    revenue_growth_percent: Optional[float]
    active_customers: int
    top_products: List[ProductPerformance]
    top_categories: List[CategoryPerformance]
    employee_leaderboard: List[EmployeeLeaderboardEntry]
    inventory_value: Decimal
    low_stock_count: int
    out_of_stock_count: int
    open_alerts: int
    headline_findings: List[str]
