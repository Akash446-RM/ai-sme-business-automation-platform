"""Analytics and dashboard schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class PeriodSummary(BaseModel):
    """Sales performance for one period compared with the previous one."""

    label: str
    period_start: date
    period_end: date
    revenue: Decimal
    transactions: int
    units_sold: int
    average_order_value: Decimal
    previous_revenue: Decimal
    revenue_growth_percent: Optional[float] = Field(
        default=None, description="Null when there is no comparable previous period"
    )
    transaction_growth_percent: Optional[float] = None


class TrendPoint(BaseModel):
    period: str
    revenue: Decimal
    transactions: int
    units_sold: int
    average_order_value: Decimal


class SalesTrend(BaseModel):
    granularity: str
    date_from: date
    date_to: date
    points: List[TrendPoint]
    total_revenue: Decimal
    total_transactions: int


class ProductPerformance(BaseModel):
    product_id: int
    name: str
    sku: str
    category: str
    units_sold: int
    revenue: Decimal
    gross_profit: Decimal
    transactions: int
    current_stock: int
    revenue_share_percent: float = 0.0
    growth_percent: Optional[float] = None


class CategoryPerformance(BaseModel):
    category: str
    units_sold: int
    revenue: Decimal
    gross_profit: Decimal
    transactions: int
    product_count: int
    revenue_share_percent: float = 0.0
    growth_percent: Optional[float] = None


class CustomerPerformance(BaseModel):
    customer_id: int
    customer_code: str
    name: str
    city: Optional[str]
    total_orders: int
    total_spent: Decimal
    average_order_value: Decimal
    last_purchase: Optional[datetime]
    revenue_share_percent: float = 0.0


class EmployeeLeaderboardEntry(BaseModel):
    employee_id: int
    name: str
    role: str
    transactions: int
    revenue: Decimal
    average_order_value: Decimal


class PaymentMix(BaseModel):
    payment_method: str
    transactions: int
    revenue: Decimal
    share_percent: float


class HourlyPattern(BaseModel):
    hour: int
    transactions: int
    revenue: Decimal


class WeekdayPattern(BaseModel):
    weekday: str
    weekday_index: int
    transactions: int
    revenue: Decimal
    average_revenue: Decimal


class RevenueAnalytics(BaseModel):
    """Everything the revenue view needs, in one response."""

    today: PeriodSummary
    this_week: PeriodSummary
    this_month: PeriodSummary
    this_year: PeriodSummary
    gross_profit: Decimal
    gross_margin_percent: float


class DashboardKpis(BaseModel):
    total_products: int
    active_products: int
    total_customers: int
    total_employees: int
    total_sales: int
    total_revenue: Decimal
    today_revenue: Decimal
    today_transactions: int
    month_revenue: Decimal
    month_growth_percent: Optional[float]
    average_order_value: Decimal
    low_stock_count: int
    out_of_stock_count: int
    inventory_value: Decimal
    open_alerts: int


class DashboardInsight(BaseModel):
    """A short, data derived observation surfaced on the dashboard."""

    type: str
    severity: str
    title: str
    message: str
    metric: Optional[str] = None
    entity_id: Optional[int] = None


class DashboardSummary(BaseModel):
    kpis: DashboardKpis
    revenue_trend: List[TrendPoint]
    top_products: List[ProductPerformance]
    category_performance: List[CategoryPerformance]
    recent_sales: List[dict]
    insights: List[DashboardInsight]
    generated_at: datetime
