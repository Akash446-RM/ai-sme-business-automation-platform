"""Business reporting.

Reports reuse the analytics and inventory services rather than re-implementing
aggregation, so a number shown in a report always matches the same number on
the dashboard.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models.alert import Alert
from app.models.enums import AlertStatus
from app.models.sale import Sale
from app.repositories.product_repository import ProductRepository
from app.schemas.analytics import TrendPoint
from app.schemas.report import (
    BusinessSummaryReport,
    CustomerReport,
    InventoryReport,
    ProductReport,
    ReportMeta,
    RevenueReport,
    SalesReport,
)
from app.services.analytics_service import AnalyticsService, money
from app.services.forecast_service import build_inventory_service

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.analytics = AnalyticsService(db)
        self.inventory = build_inventory_service(db)
        self.product_repo = ProductRepository(db)

    # -- helpers ----------------------------------------------------------
    def _window(
        self, date_from: Optional[date], date_to: Optional[date], default_days: int = 30
    ) -> Tuple[date, date]:
        if date_from and date_to:
            return date_from, date_to
        return self.analytics.default_window(default_days)

    def _meta(
        self,
        report_type: str,
        title: str,
        date_from: date,
        date_to: date,
        **filters,
    ) -> ReportMeta:
        return ReportMeta(
            report_type=report_type,
            title=title,
            date_from=date_from,
            date_to=date_to,
            generated_at=datetime.now(),
            filters={key: value for key, value in filters.items() if value is not None},
        )

    # -- reports ----------------------------------------------------------
    def sales_report(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> SalesReport:
        date_from, date_to = self._window(date_from, date_to)
        summary = self.analytics.period_summary("Sales report", date_from, date_to)
        gross = self.analytics.repo.gross_profit(date_from, date_to)
        revenue = float(summary.revenue)

        return SalesReport(
            meta=self._meta("sales", "Sales Report", date_from, date_to),
            total_revenue=summary.revenue,
            total_transactions=summary.transactions,
            total_units=summary.units_sold,
            average_order_value=summary.average_order_value,
            gross_profit=money(gross),
            gross_margin_percent=round(gross / revenue * 100, 2) if revenue else 0.0,
            previous_revenue=summary.previous_revenue,
            revenue_growth_percent=summary.revenue_growth_percent,
            daily_breakdown=self.analytics.sales_trend(date_from, date_to, "day").points,
            payment_mix=self.analytics.payment_mix(date_from, date_to),
        )

    def revenue_report(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> RevenueReport:
        date_from, date_to = self._window(date_from, date_to, default_days=365)
        monthly = self.analytics.sales_trend(date_from, date_to, "month").points
        categories = self.analytics.category_performance(date_from, date_to)

        best = max(monthly, key=lambda point: point.revenue) if monthly else None
        worst = min(monthly, key=lambda point: point.revenue) if monthly else None

        return RevenueReport(
            meta=self._meta("revenue", "Revenue Report", date_from, date_to),
            monthly_breakdown=monthly,
            category_breakdown=categories,
            total_revenue=money(sum(float(point.revenue) for point in monthly)),
            total_gross_profit=money(self.analytics.repo.gross_profit(date_from, date_to)),
            best_month=best,
            worst_month=worst,
        )

    def inventory_report(self, horizon_days: int = 7) -> InventoryReport:
        today = self.analytics.reference_date()
        overview = self.inventory.overview()
        params = PageParams(page=1, page_size=50)

        low_items, _ = self.inventory.stock_items(params, status_filter="low")
        out_items, _ = self.inventory.stock_items(params, status_filter="out_of_stock")

        return InventoryReport(
            meta=self._meta(
                "inventory",
                "Inventory Report",
                today,
                today,
                horizon_days=horizon_days,
            ),
            total_products=overview.total_products,
            total_units=overview.total_units,
            total_stock_value=overview.total_stock_value,
            low_stock_items=low_items,
            out_of_stock_items=out_items,
            dead_stock_items=self.inventory.dead_stock(20),
            valuation_by_category=self.inventory.valuation(),
            reorder_recommendations=self.inventory.reorder_recommendations(
                horizon_days=horizon_days, limit=30
            ),
        )

    def product_report(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 15,
    ) -> ProductReport:
        date_from, date_to = self._window(date_from, date_to)
        return ProductReport(
            meta=self._meta("product", "Product Performance Report", date_from, date_to),
            best_performers=self.analytics.product_performance(
                date_from, date_to, limit=limit
            ),
            worst_performers=self.analytics.product_performance(
                date_from, date_to, limit=limit, ascending=True
            ),
            category_performance=self.analytics.category_performance(date_from, date_to),
        )

    def customer_report(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 20,
    ) -> CustomerReport:
        date_from, date_to = self._window(date_from, date_to, default_days=90)
        top = self.analytics.top_customers(date_from, date_to, limit)
        active = self.analytics.repo.active_customer_count(date_from, date_to)

        start, end = (
            datetime.combine(date_from, datetime.min.time()),
            datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
        )
        repeat_count = int(
            self.db.execute(
                select(func.count()).select_from(
                    select(Sale.customer_id)
                    .where(
                        Sale.sale_date >= start,
                        Sale.sale_date < end,
                        Sale.customer_id.is_not(None),
                    )
                    .group_by(Sale.customer_id)
                    .having(func.count(Sale.id) > 1)
                    .subquery()
                )
            ).scalar_one()
        )
        revenue, _, _ = self.analytics.repo.period_totals(date_from, date_to)

        return CustomerReport(
            meta=self._meta("customer", "Customer Report", date_from, date_to),
            top_customers=top,
            total_active_customers=active,
            repeat_customer_count=repeat_count,
            repeat_rate_percent=round(repeat_count / active * 100, 2) if active else 0.0,
            average_customer_value=money(revenue / active) if active else money(0),
        )

    def business_summary(
        self, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> BusinessSummaryReport:
        date_from, date_to = self._window(date_from, date_to)
        summary = self.analytics.period_summary("Business summary", date_from, date_to)
        gross = self.analytics.repo.gross_profit(date_from, date_to)
        revenue = float(summary.revenue)

        top_products = self.analytics.product_performance(date_from, date_to, limit=5)
        top_categories = self.analytics.category_performance(date_from, date_to)[:5]
        overview = self.inventory.overview()
        open_alerts = int(
            self.db.execute(
                select(func.count(Alert.id)).where(Alert.status == AlertStatus.OPEN)
            ).scalar_one()
        )

        findings = self._headline_findings(
            summary=summary, top_products=top_products, top_categories=top_categories,
            overview=overview,
        )

        return BusinessSummaryReport(
            meta=self._meta("business_summary", "Business Summary", date_from, date_to),
            revenue=summary.revenue,
            gross_profit=money(gross),
            gross_margin_percent=round(gross / revenue * 100, 2) if revenue else 0.0,
            transactions=summary.transactions,
            units_sold=summary.units_sold,
            average_order_value=summary.average_order_value,
            revenue_growth_percent=summary.revenue_growth_percent,
            active_customers=self.analytics.repo.active_customer_count(date_from, date_to),
            top_products=top_products,
            top_categories=top_categories,
            employee_leaderboard=self.analytics.employee_leaderboard(
                date_from, date_to, limit=5
            ),
            inventory_value=overview.total_stock_value,
            low_stock_count=overview.low_stock_count,
            out_of_stock_count=overview.out_of_stock_count,
            open_alerts=open_alerts,
            headline_findings=findings,
        )

    @staticmethod
    def _headline_findings(*, summary, top_products, top_categories, overview) -> List[str]:
        findings: List[str] = []
        if summary.revenue_growth_percent is not None:
            direction = "up" if summary.revenue_growth_percent >= 0 else "down"
            findings.append(
                f"Revenue is {direction} {abs(summary.revenue_growth_percent):.1f}% "
                f"compared with the previous period of equal length."
            )
        if top_products:
            best = top_products[0]
            findings.append(
                f"'{best.name}' is the top product with {float(best.revenue):,.0f} in revenue "
                f"from {best.units_sold} units."
            )
        if top_categories:
            leader = top_categories[0]
            findings.append(
                f"'{leader.category}' is the strongest category, contributing "
                f"{leader.revenue_share_percent:.1f}% of revenue in this period."
            )
        if overview.out_of_stock_count:
            findings.append(
                f"{overview.out_of_stock_count} products are out of stock and are losing "
                f"potential sales right now."
            )
        if overview.low_stock_count:
            findings.append(
                f"{overview.low_stock_count} products are at or below their reorder level."
            )
        if overview.dead_stock_count:
            findings.append(
                f"{overview.dead_stock_count} products have not sold in 90 days, "
                f"tying up working capital."
            )
        return findings
