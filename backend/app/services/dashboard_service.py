"""Dashboard assembly.

Every figure shown on the dashboard is computed from the database. Nothing is
hardcoded, and insights are generated from the same numbers the charts show.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.enums import AlertStatus
from app.repositories.customer_repository import CustomerRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.sale_repository import SaleRepository
from app.schemas.analytics import (
    DashboardInsight,
    DashboardKpis,
    DashboardSummary,
)
from app.services.analytics_service import AnalyticsService, money
from app.services.forecast_service import build_inventory_service

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.analytics = AnalyticsService(db)
        self.product_repo = ProductRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.sale_repo = SaleRepository(db)

    def kpis(self) -> DashboardKpis:
        reference = self.analytics.reference_date()
        month_start = reference.replace(day=1)

        today_revenue, today_transactions, _ = self.analytics.repo.period_totals(
            reference, reference
        )
        month_revenue, _, _ = self.analytics.repo.period_totals(month_start, reference)

        previous_month_end = month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)
        # Compare like with like: same number of elapsed days.
        elapsed_days = (reference - month_start).days
        previous_comparable_end = min(
            previous_month_start + timedelta(days=elapsed_days), previous_month_end
        )
        previous_month_revenue, _, _ = self.analytics.repo.period_totals(
            previous_month_start, previous_comparable_end
        )

        total_sales = self.sale_repo.count_sales()
        total_revenue = self.sale_repo.total_revenue()
        open_alerts = int(
            self.db.execute(
                select(func.count(Alert.id)).where(Alert.status == AlertStatus.OPEN)
            ).scalar_one()
        )

        from app.services.analytics_service import growth_percent

        return DashboardKpis(
            total_products=int(
                self.db.execute(
                    select(func.count()).select_from(self.product_repo.model)
                ).scalar_one()
            ),
            active_products=self.product_repo.count_active(),
            total_customers=self.customer_repo.count_active(),
            total_employees=self.employee_repo.count_active(),
            total_sales=total_sales,
            total_revenue=money(total_revenue),
            today_revenue=money(today_revenue),
            today_transactions=today_transactions,
            month_revenue=money(month_revenue),
            month_growth_percent=growth_percent(month_revenue, previous_month_revenue),
            average_order_value=money(total_revenue / total_sales) if total_sales else money(0),
            low_stock_count=self.product_repo.count_low_stock(),
            out_of_stock_count=self.product_repo.count_out_of_stock(),
            inventory_value=money(self.product_repo.total_stock_value()),
            open_alerts=open_alerts,
        )

    def insights(self, limit: int = 6) -> List[DashboardInsight]:
        """Derive short, factual observations from current data."""
        insights: List[DashboardInsight] = []

        trend = self.analytics.detect_sales_trend(window_days=14)
        change = trend["revenue_change_percent"]
        if change is not None:
            if trend["direction"] == "growing":
                insights.append(
                    DashboardInsight(
                        type="sales_growth",
                        severity="info",
                        title="Sales are growing",
                        message=(
                            f"Revenue over the last 14 days is {change:.1f}% higher than the "
                            f"previous 14 days "
                            f"({trend['current_period']['revenue']:,.0f} vs "
                            f"{trend['previous_period']['revenue']:,.0f})."
                        ),
                        metric=f"{change:.1f}%",
                    )
                )
            elif trend["direction"] == "declining":
                insights.append(
                    DashboardInsight(
                        type="sales_decline",
                        severity="high",
                        title="Sales are declining",
                        message=(
                            f"Revenue over the last 14 days is {abs(change):.1f}% lower than the "
                            f"previous 14 days. Review pricing, stock availability and "
                            f"customer follow ups."
                        ),
                        metric=f"{change:.1f}%",
                    )
                )

        out_of_stock = self.product_repo.count_out_of_stock()
        if out_of_stock:
            insights.append(
                DashboardInsight(
                    type="out_of_stock",
                    severity="critical",
                    title=f"{out_of_stock} products are out of stock",
                    message=(
                        f"{out_of_stock} active products currently have zero stock and "
                        f"cannot be sold. Restock them to avoid lost revenue."
                    ),
                    metric=str(out_of_stock),
                )
            )

        low_stock = self.product_repo.count_low_stock()
        if low_stock:
            insights.append(
                DashboardInsight(
                    type="low_stock",
                    severity="high",
                    title=f"{low_stock} products are below their reorder level",
                    message=(
                        f"{low_stock} products have fallen to or below their reorder point. "
                        f"Check the inventory recommendations for suggested quantities."
                    ),
                    metric=str(low_stock),
                )
            )

        shifts = self.analytics.product_demand_shifts(window_days=30, limit=3)
        for entry in shifts["rising_demand"][:2]:
            insights.append(
                DashboardInsight(
                    type="demand_surge",
                    severity="medium",
                    title=f"Rising demand: {entry['name']}",
                    message=(
                        f"Sold {entry['current_units']} units in the last 30 days versus "
                        f"{entry['previous_units']} in the prior 30 days "
                        f"({entry['change_percent']:.0f}% change). Current stock is "
                        f"{entry['current_stock']} units."
                    ),
                    metric=f"+{entry['change_percent']:.0f}%",
                    entity_id=entry["product_id"],
                )
            )
        for entry in shifts["falling_demand"][:1]:
            insights.append(
                DashboardInsight(
                    type="demand_drop",
                    severity="medium",
                    title=f"Falling demand: {entry['name']}",
                    message=(
                        f"Sold {entry['current_units']} units in the last 30 days versus "
                        f"{entry['previous_units']} in the prior 30 days "
                        f"({entry['change_percent']:.0f}% change). Avoid over ordering."
                    ),
                    metric=f"{entry['change_percent']:.0f}%",
                    entity_id=entry["product_id"],
                )
            )

        top = self.analytics.product_performance(limit=1)
        if top:
            best = top[0]
            insights.append(
                DashboardInsight(
                    type="top_product",
                    severity="info",
                    title=f"Best seller: {best.name}",
                    message=(
                        f"Generated {float(best.revenue):,.0f} in revenue from "
                        f"{best.units_sold} units over the last 30 days, which is "
                        f"{best.revenue_share_percent:.1f}% of top product revenue."
                    ),
                    metric=f"{float(best.revenue):,.0f}",
                    entity_id=best.product_id,
                )
            )

        severity_rank = {"critical": 0, "high": 1, "medium": 2, "info": 3}
        insights.sort(key=lambda item: severity_rank.get(item.severity, 4))
        return insights[:limit]

    def summary(self) -> DashboardSummary:
        date_from, date_to = self.analytics.default_window(30)
        trend = self.analytics.sales_trend(date_from, date_to, "day")
        recent = [
            {
                "bill_no": sale.bill_no,
                "customer_name": sale.customer_name,
                "employee_name": sale.employee_name,
                "item_count": sale.item_count,
                "total_amount": float(sale.total_amount),
                "sale_date": sale.sale_date.isoformat(),
            }
            for sale in self._recent_sales(8)
        ]

        return DashboardSummary(
            kpis=self.kpis(),
            revenue_trend=trend.points,
            top_products=self.analytics.product_performance(limit=8),
            category_performance=self.analytics.category_performance(),
            recent_sales=recent,
            insights=self.insights(),
            generated_at=datetime.now(),
        )

    def _recent_sales(self, limit: int):
        from app.services.sales_service import SalesService

        return SalesService(self.db).recent(limit)
