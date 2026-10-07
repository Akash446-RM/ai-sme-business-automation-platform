"""Business analytics endpoints."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.analytics import (
    CategoryPerformance,
    CustomerPerformance,
    EmployeeLeaderboardEntry,
    HourlyPattern,
    PaymentMix,
    PeriodSummary,
    ProductPerformance,
    RevenueAnalytics,
    SalesTrend,
    WeekdayPattern,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/revenue", response_model=RevenueAnalytics, summary="Revenue at a glance")
def revenue(db: DbSession, _: CurrentUser) -> RevenueAnalytics:
    return AnalyticsService(db).revenue_analytics()


@router.get("/summary", response_model=PeriodSummary, summary="Summary for a date range")
def summary(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> PeriodSummary:
    service = AnalyticsService(db)
    if date_from is None or date_to is None:
        date_from, date_to = service.default_window(30)
    return service.period_summary("Selected period", date_from, date_to)


@router.get("/sales-trend", response_model=SalesTrend, summary="Revenue trend over time")
def sales_trend(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    granularity: str = Query("day", pattern="^(day|week|month)$"),
) -> SalesTrend:
    return AnalyticsService(db).sales_trend(date_from, date_to, granularity)


@router.get(
    "/products",
    response_model=List[ProductPerformance],
    summary="Product performance ranking",
)
def products(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(10, ge=1, le=100),
    order: str = Query("top", pattern="^(top|bottom)$"),
    category: Optional[str] = Query(None, max_length=80),
) -> List[ProductPerformance]:
    return AnalyticsService(db).product_performance(
        date_from, date_to, limit=limit, ascending=order == "bottom", category=category
    )


@router.get(
    "/categories",
    response_model=List[CategoryPerformance],
    summary="Category performance",
)
def categories(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[CategoryPerformance]:
    return AnalyticsService(db).category_performance(date_from, date_to)


@router.get(
    "/customers",
    response_model=List[CustomerPerformance],
    summary="Top customers by spend",
)
def customers(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(10, ge=1, le=100),
) -> List[CustomerPerformance]:
    return AnalyticsService(db).top_customers(date_from, date_to, limit)


@router.get(
    "/employees",
    response_model=List[EmployeeLeaderboardEntry],
    summary="Employee sales leaderboard",
)
def employees(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(10, ge=1, le=100),
) -> List[EmployeeLeaderboardEntry]:
    return AnalyticsService(db).employee_leaderboard(date_from, date_to, limit)


@router.get("/payment-mix", response_model=List[PaymentMix], summary="Payment method mix")
def payment_mix(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[PaymentMix]:
    return AnalyticsService(db).payment_mix(date_from, date_to)


@router.get(
    "/hourly-pattern",
    response_model=List[HourlyPattern],
    summary="Transactions by hour of day",
)
def hourly_pattern(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[HourlyPattern]:
    return AnalyticsService(db).hourly_pattern(date_from, date_to)


@router.get(
    "/weekday-pattern",
    response_model=List[WeekdayPattern],
    summary="Transactions by day of week",
)
def weekday_pattern(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[WeekdayPattern]:
    return AnalyticsService(db).weekday_pattern(date_from, date_to)


@router.get("/demand-shifts", summary="Products with rising or falling demand")
def demand_shifts(
    db: DbSession,
    _: CurrentUser,
    window_days: int = Query(30, ge=7, le=180),
    threshold_percent: float = Query(30.0, ge=5, le=500),
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    return AnalyticsService(db).product_demand_shifts(window_days, threshold_percent, limit)


@router.get("/sales-trend-signal", summary="Is the business growing or declining?")
def sales_trend_signal(
    db: DbSession, _: CurrentUser, window_days: int = Query(14, ge=7, le=90)
) -> dict:
    return AnalyticsService(db).detect_sales_trend(window_days)
