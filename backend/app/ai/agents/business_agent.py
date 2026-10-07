"""Business agent.

Handles broad "how is my business doing" questions, alert summaries and
anything the router could not classify. For unknown questions it states
honestly that it cannot answer and offers what it can do, rather than guessing.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.context import NO_DATA_MESSAGE, BusinessContext, money
from app.ai.router import SUGGESTED_QUESTIONS, Intent, RoutingResult
from app.services.automation_service import AutomationService
from app.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)


class BusinessAgent:
    """Cross domain overview and fallback handling."""

    name = "business_agent"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.dashboard = DashboardService(db)

    def handle(self, routing: RoutingResult, question: str) -> BusinessContext:
        context = BusinessContext(intent=str(routing.intent), agent=self.name)

        if routing.intent == Intent.ALERTS:
            self._alerts(context)
        elif routing.intent == Intent.UNKNOWN:
            self._unknown(context)
        else:
            self._overview(context)
        return context

    def _overview(self, context: BusinessContext) -> None:
        kpis = self.dashboard.kpis()
        insights = self.dashboard.insights(limit=5)
        context.add_source("dashboard aggregates over the sales and product tables")

        if kpis.total_sales == 0:
            context.has_data = False
            context.summary = "There are no recorded sales yet, so there is nothing to summarise."
            return

        growth = (
            f" That is {kpis.month_growth_percent:+.1f}% versus the same point last month."
            if kpis.month_growth_percent is not None
            else ""
        )
        context.summary = (
            f"The business has recorded {kpis.total_sales:,} sales worth "
            f"{money(float(kpis.total_revenue))} in total. This month's revenue is "
            f"{money(float(kpis.month_revenue))}.{growth}"
        )
        context.add_fact(f"Total revenue: {money(float(kpis.total_revenue))}")
        context.add_fact(f"Revenue this month: {money(float(kpis.month_revenue))}")
        context.add_fact(f"Revenue today: {money(float(kpis.today_revenue))} "
                         f"from {kpis.today_transactions} transactions")
        context.add_fact(f"Average order value: {money(float(kpis.average_order_value))}")
        context.add_fact(f"Active products: {kpis.active_products}")
        context.add_fact(f"Customers: {kpis.total_customers}")
        context.add_fact(f"Inventory value: {money(float(kpis.inventory_value))}")
        context.add_fact(
            f"Stock warnings: {kpis.low_stock_count} low, "
            f"{kpis.out_of_stock_count} out of stock"
        )
        if kpis.open_alerts:
            context.add_fact(f"Open alerts: {kpis.open_alerts}")

        if insights:
            context.add_detail(
                "What needs attention:\n"
                + "\n".join(
                    f"- [{insight.severity}] {insight.title}: {insight.message}"
                    for insight in insights
                )
            )
        context.data = {
            "kpis": kpis.model_dump(mode="json"),
            "insights": [insight.model_dump(mode="json") for insight in insights],
        }

    def _alerts(self, context: BusinessContext) -> None:
        automation = AutomationService(self.db)
        summary = automation.summary()
        context.add_source("automation engine alerts")

        if summary.total_open == 0:
            context.summary = (
                "There are no open alerts. Run an inventory scan if you want the "
                "system to re-check stock levels and demand trends now."
            )
            context.add_fact("Open alerts: 0")
            return

        context.summary = (
            f"There are {summary.total_open} open alerts: {summary.critical} critical, "
            f"{summary.high} high, {summary.medium} medium and {summary.low} low priority."
        )
        context.add_fact(f"Critical: {summary.critical}")
        context.add_fact(f"High: {summary.high}")
        context.add_fact(f"Medium: {summary.medium}")
        context.add_fact(f"Low or informational: {summary.low}")

        from app.core.pagination import PageParams

        alerts, _ = automation.list_alerts(PageParams(page=1, page_size=6), status="open")
        if alerts:
            context.add_detail(
                "Most important alerts:\n"
                + "\n".join(
                    f"- [{alert.severity}] {alert.title}: {alert.description}"
                    + (
                        f" Recommended action: {alert.recommended_action}"
                        if alert.recommended_action
                        else ""
                    )
                    for alert in alerts
                )
            )
        context.data = {"summary": summary.model_dump(mode="json")}

    def _unknown(self, context: BusinessContext) -> None:
        """Refuse to guess. State the limitation and offer real options."""
        context.has_data = False
        context.summary = NO_DATA_MESSAGE
        context.suggestions = SUGGESTED_QUESTIONS[:5]
        context.add_detail(
            "Questions I can answer:\n"
            + "\n".join(f"- {question}" for question in SUGGESTED_QUESTIONS[:6])
        )
