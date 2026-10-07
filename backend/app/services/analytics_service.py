"""Business analytics.

Turns aggregation results into the comparative, growth aware figures a business
owner actually reads: how did this period compare with the last one, which
products and categories are moving, who are the best customers.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.repositories.analytics_repository import AnalyticsRepository
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
    TrendPoint,
    WeekdayPattern,
)

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = list(calendar.day_name)  # Monday .. Sunday


def growth_percent(current: float, previous: float) -> Optional[float]:
    """Percentage change, or None when there is no comparable baseline."""
    if previous <= 0:
        return None
    return round((current - previous) / previous * 100, 2)


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(round(float(value), 2)))


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AnalyticsRepository(db)

    # -- reference date ---------------------------------------------------
    def reference_date(self) -> date:
        """Latest date with data, so demo databases never look empty."""
        _, latest = self.repo.data_range()
        return latest.date() if latest else date.today()

    def default_window(self, days: int = 30) -> Tuple[date, date]:
        end = self.reference_date()
        return end - timedelta(days=days - 1), end

    # -- period summaries -------------------------------------------------
    def period_summary(
        self, label: str, date_from: date, date_to: date
    ) -> PeriodSummary:
        revenue, transactions, units = self.repo.period_totals(date_from, date_to)

        span = (date_to - date_from).days + 1
        previous_to = date_from - timedelta(days=1)
        previous_from = previous_to - timedelta(days=span - 1)
        previous_revenue, previous_transactions, _ = self.repo.period_totals(
            previous_from, previous_to
        )

        return PeriodSummary(
            label=label,
            period_start=date_from,
            period_end=date_to,
            revenue=money(revenue),
            transactions=transactions,
            units_sold=units,
            average_order_value=money(revenue / transactions) if transactions else money(0),
            previous_revenue=money(previous_revenue),
            revenue_growth_percent=growth_percent(revenue, previous_revenue),
            transaction_growth_percent=growth_percent(transactions, previous_transactions),
        )

    def revenue_analytics(self) -> RevenueAnalytics:
        today = self.reference_date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        gross = self.repo.gross_profit(month_start, today)
        month_revenue, _, _ = self.repo.period_totals(month_start, today)

        return RevenueAnalytics(
            today=self.period_summary("Today", today, today),
            this_week=self.period_summary("This week", week_start, today),
            this_month=self.period_summary("This month", month_start, today),
            this_year=self.period_summary("This year", year_start, today),
            gross_profit=money(gross),
            gross_margin_percent=(
                round(gross / month_revenue * 100, 2) if month_revenue > 0 else 0.0
            ),
        )

    # -- trends -----------------------------------------------------------
    def sales_trend(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        granularity: str = "day",
    ) -> SalesTrend:
        if date_from is None or date_to is None:
            date_from, date_to = self.default_window(30)

        rows = self.repo.revenue_trend(date_from, date_to, granularity)
        points = [
            TrendPoint(
                period=str(row[0]),
                revenue=money(row[1] or 0),
                transactions=int(row[2] or 0),
                units_sold=int(row[3] or 0),
                average_order_value=(
                    money(float(row[1] or 0) / int(row[2])) if int(row[2] or 0) else money(0)
                ),
            )
            for row in rows
        ]
        return SalesTrend(
            granularity=granularity,
            date_from=date_from,
            date_to=date_to,
            points=points,
            total_revenue=money(sum(float(point.revenue) for point in points)),
            total_transactions=sum(point.transactions for point in points),
        )

    # -- products ---------------------------------------------------------
    def product_performance(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        *,
        limit: int = 10,
        ascending: bool = False,
        category: Optional[str] = None,
        with_growth: bool = True,
    ) -> List[ProductPerformance]:
        if date_from is None or date_to is None:
            date_from, date_to = self.default_window(30)

        rows = self.repo.product_performance(
            date_from, date_to, limit=limit, ascending=ascending, category=category
        )
        total_revenue = sum(float(row[5] or 0) for row in rows) or 1.0

        previous_map: Dict[int, float] = {}
        if with_growth:
            span = (date_to - date_from).days + 1
            previous_to = date_from - timedelta(days=1)
            previous_map = self.repo.product_revenue_map(
                previous_to - timedelta(days=span - 1), previous_to
            )

        results: List[ProductPerformance] = []
        for row in rows:
            revenue = float(row[5] or 0)
            product_id = int(row[0])
            results.append(
                ProductPerformance(
                    product_id=product_id,
                    name=row[1],
                    sku=row[2],
                    category=row[3],
                    units_sold=int(row[4] or 0),
                    revenue=money(revenue),
                    gross_profit=money(row[6] or 0),
                    transactions=int(row[7] or 0),
                    current_stock=int(row[8] or 0),
                    revenue_share_percent=round(revenue / total_revenue * 100, 2),
                    growth_percent=(
                        growth_percent(revenue, previous_map.get(product_id, 0.0))
                        if with_growth
                        else None
                    ),
                )
            )
        return results

    # -- categories -------------------------------------------------------
    def category_performance(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> List[CategoryPerformance]:
        if date_from is None or date_to is None:
            date_from, date_to = self.default_window(30)

        rows = self.repo.category_performance(date_from, date_to)
        total_revenue = sum(float(row[2] or 0) for row in rows) or 1.0

        span = (date_to - date_from).days + 1
        previous_to = date_from - timedelta(days=1)
        previous_map = self.repo.category_revenue_map(
            previous_to - timedelta(days=span - 1), previous_to
        )

        return [
            CategoryPerformance(
                category=row[0],
                units_sold=int(row[1] or 0),
                revenue=money(row[2] or 0),
                gross_profit=money(row[3] or 0),
                transactions=int(row[4] or 0),
                product_count=int(row[5] or 0),
                revenue_share_percent=round(float(row[2] or 0) / total_revenue * 100, 2),
                growth_percent=growth_percent(
                    float(row[2] or 0), previous_map.get(str(row[0]), 0.0)
                ),
            )
            for row in rows
        ]

    # -- customers and employees -----------------------------------------
    def top_customers(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 10,
    ) -> List[CustomerPerformance]:
        if date_from is None or date_to is None:
            date_from, date_to = self.default_window(90)

        rows = self.repo.top_customers(date_from, date_to, limit)
        period_revenue, _, _ = self.repo.period_totals(date_from, date_to)
        denominator = period_revenue or 1.0

        return [
            CustomerPerformance(
                customer_id=int(row[0]),
                customer_code=row[1],
                name=row[2],
                city=row[3],
                total_orders=int(row[4] or 0),
                total_spent=money(row[5] or 0),
                average_order_value=(
                    money(float(row[5] or 0) / int(row[4])) if int(row[4] or 0) else money(0)
                ),
                last_purchase=row[6],
                revenue_share_percent=round(float(row[5] or 0) / denominator * 100, 2),
            )
            for row in rows
        ]

    def employee_leaderboard(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 10,
    ) -> List[EmployeeLeaderboardEntry]:
        if date_from is None or date_to is None:
            date_from, date_to = self.default_window(30)

        return [
            EmployeeLeaderboardEntry(
                employee_id=int(row[0]),
                name=row[1],
                role=row[2],
                transactions=int(row[3] or 0),
                revenue=money(row[4] or 0),
                average_order_value=(
                    money(float(row[4] or 0) / int(row[3])) if int(row[3] or 0) else money(0)
                ),
            )
            for row in self.repo.employee_leaderboard(date_from, date_to, limit)
        ]

    # -- behavioural patterns ---------------------------------------------
    def payment_mix(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> List[PaymentMix]:
        if date_from is None or date_to is None:
            date_from, date_to = self.default_window(30)

        rows = self.repo.payment_mix(date_from, date_to)
        total = sum(float(row[2] or 0) for row in rows) or 1.0
        return [
            PaymentMix(
                payment_method=str(row[0]),
                transactions=int(row[1] or 0),
                revenue=money(row[2] or 0),
                share_percent=round(float(row[2] or 0) / total * 100, 2),
            )
            for row in rows
        ]

    def hourly_pattern(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> List[HourlyPattern]:
        if date_from is None or date_to is None:
            date_from, date_to = self.default_window(30)
        return [
            HourlyPattern(
                hour=int(row[0]), transactions=int(row[1] or 0), revenue=money(row[2] or 0)
            )
            for row in self.repo.hourly_pattern(date_from, date_to)
        ]

    def weekday_pattern(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> List[WeekdayPattern]:
        if date_from is None or date_to is None:
            date_from, date_to = self.default_window(90)
        return [
            WeekdayPattern(
                weekday=WEEKDAY_NAMES[index],
                weekday_index=index,
                transactions=transactions,
                revenue=money(revenue),
                average_revenue=money(revenue / days if days else 0),
            )
            for index, transactions, revenue, days in self.repo.weekday_pattern(
                date_from, date_to
            )
        ]

    # -- trend detection used by automation and AI ------------------------
    def detect_sales_trend(self, window_days: int = 14) -> dict:
        """Compare the most recent window with the one before it."""
        end = self.reference_date()
        current_from = end - timedelta(days=window_days - 1)
        previous_to = current_from - timedelta(days=1)
        previous_from = previous_to - timedelta(days=window_days - 1)

        current_revenue, current_transactions, _ = self.repo.period_totals(current_from, end)
        previous_revenue, previous_transactions, _ = self.repo.period_totals(
            previous_from, previous_to
        )
        change = growth_percent(current_revenue, previous_revenue)

        if change is None:
            direction = "unknown"
        elif change >= 10:
            direction = "growing"
        elif change <= -10:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "window_days": window_days,
            "current_period": {"from": current_from, "to": end, "revenue": current_revenue,
                               "transactions": current_transactions},
            "previous_period": {"from": previous_from, "to": previous_to,
                                "revenue": previous_revenue,
                                "transactions": previous_transactions},
            "revenue_change_percent": change,
            "direction": direction,
        }

    def product_demand_shifts(
        self, window_days: int = 30, threshold_percent: float = 30.0, limit: int = 10
    ) -> dict:
        """Products whose recent demand differs sharply from the prior window."""
        end = self.reference_date()
        current_from = end - timedelta(days=window_days - 1)
        previous_to = current_from - timedelta(days=1)
        previous_from = previous_to - timedelta(days=window_days - 1)

        current = self.repo.product_units_map(current_from, end)
        previous = self.repo.product_units_map(previous_from, previous_to)

        from app.models.product import Product

        product_ids = set(current) | set(previous)
        names = {
            product.id: (product.name, product.category, product.stock)
            for product in self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        } if product_ids else {}

        rising: List[dict] = []
        falling: List[dict] = []
        for product_id in product_ids:
            current_units = current.get(product_id, 0)
            previous_units = previous.get(product_id, 0)
            # Ignore products with negligible volume to avoid noisy percentages.
            if previous_units < 5 and current_units < 5:
                continue
            change = growth_percent(current_units, previous_units)
            if change is None:
                continue
            name, category, stock = names.get(product_id, ("Unknown", "Unknown", 0))
            entry = {
                "product_id": product_id,
                "name": name,
                "category": category,
                "current_stock": stock,
                "current_units": current_units,
                "previous_units": previous_units,
                "change_percent": change,
            }
            if change >= threshold_percent:
                rising.append(entry)
            elif change <= -threshold_percent:
                falling.append(entry)

        rising.sort(key=lambda item: item["change_percent"], reverse=True)
        falling.sort(key=lambda item: item["change_percent"])
        return {
            "window_days": window_days,
            "threshold_percent": threshold_percent,
            "rising_demand": rising[:limit],
            "falling_demand": falling[:limit],
        }
