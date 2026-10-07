"""Analytics agent.

Answers questions about sales, revenue, products, categories, customers,
employees and trends by calling the same analytics service the dashboard uses,
so the assistant and the charts can never disagree.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.context import BusinessContext, money, resolve_period
from app.ai.router import Intent, RoutingResult
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class AnalyticsAgent:
    """Retrieves business performance facts."""

    name = "analytics_agent"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.analytics = AnalyticsService(db)

    def handle(self, routing: RoutingResult, question: str) -> BusinessContext:
        context = BusinessContext(intent=str(routing.intent), agent=self.name)
        reference = self.analytics.reference_date()
        date_from, date_to, label = resolve_period(routing.period, reference)
        context.period_label = label

        handlers = {
            Intent.SALES_PERFORMANCE: self._sales_performance,
            Intent.REVENUE: self._revenue,
            Intent.TOP_PRODUCTS: self._top_products,
            Intent.WORST_PRODUCTS: self._worst_products,
            Intent.CATEGORY_PERFORMANCE: self._categories,
            Intent.TOP_CUSTOMERS: self._customers,
            Intent.EMPLOYEE_PERFORMANCE: self._employees,
            Intent.DEMAND_TREND: self._demand_trend,
            Intent.SALES_FORECAST: self._sales_forecast,
        }
        handler = handlers.get(routing.intent, self._sales_performance)
        handler(context, date_from, date_to, routing)
        return context

    # -- handlers ---------------------------------------------------------
    def _sales_performance(self, context, date_from, date_to, routing) -> None:
        summary = self.analytics.period_summary("Selected period", date_from, date_to)
        context.add_source("sales table (aggregated)")

        if summary.transactions == 0:
            context.has_data = False
            context.summary = f"There were no recorded sales in {context.period_label}."
            return

        change = summary.revenue_growth_percent
        direction = (
            "up" if change is not None and change >= 0 else "down"
        ) if change is not None else None

        context.summary = (
            f"In {context.period_label} the business recorded "
            f"{money(float(summary.revenue))} of revenue across "
            f"{summary.transactions:,} transactions."
        )
        context.add_fact(f"Revenue: {money(float(summary.revenue))}")
        context.add_fact(f"Transactions: {summary.transactions:,}")
        context.add_fact(f"Units sold: {summary.units_sold:,}")
        context.add_fact(
            f"Average order value: {money(float(summary.average_order_value))}"
        )
        if change is not None:
            context.add_fact(
                f"Revenue is {direction} {abs(change):.1f}% versus the previous "
                f"period of equal length "
                f"({money(float(summary.previous_revenue))})."
            )
        context.data = {
            "revenue": float(summary.revenue),
            "transactions": summary.transactions,
            "units_sold": summary.units_sold,
            "average_order_value": float(summary.average_order_value),
            "growth_percent": change,
            "period": {"from": str(date_from), "to": str(date_to)},
        }

    def _revenue(self, context, date_from, date_to, routing) -> None:
        self._sales_performance(context, date_from, date_to, routing)
        gross = self.analytics.repo.gross_profit(date_from, date_to)
        revenue = context.data.get("revenue", 0)
        if revenue:
            margin = gross / revenue * 100
            context.add_fact(f"Gross profit: {money(gross)} ({margin:.1f}% margin)")
            context.data["gross_profit"] = round(gross, 2)
            context.data["gross_margin_percent"] = round(margin, 2)
            context.add_source("sale_items cost snapshot")

        # A revenue question often means "why did it move?", so include drivers.
        categories = self.analytics.category_performance(date_from, date_to)
        movers = [row for row in categories if row.growth_percent is not None]
        if movers:
            best = max(movers, key=lambda row: row.growth_percent)
            worst = min(movers, key=lambda row: row.growth_percent)
            context.add_detail(
                "Category movement versus the previous period:\n"
                f"- Strongest: {best.category} at {best.growth_percent:+.1f}% "
                f"({money(float(best.revenue))})\n"
                f"- Weakest: {worst.category} at {worst.growth_percent:+.1f}% "
                f"({money(float(worst.revenue))})"
            )

    def _top_products(self, context, date_from, date_to, routing) -> None:
        products = self.analytics.product_performance(date_from, date_to, limit=5)
        context.add_source("sale_items joined to products")

        if not products:
            context.has_data = False
            context.summary = f"No products were sold in {context.period_label}."
            return

        best = products[0]
        context.summary = (
            f"Your best selling product in {context.period_label} is "
            f"'{best.name}' with {money(float(best.revenue))} of revenue from "
            f"{best.units_sold:,} units."
        )
        lines = []
        for position, product in enumerate(products, start=1):
            growth = (
                f", {product.growth_percent:+.0f}% versus the previous period"
                if product.growth_percent is not None
                else ""
            )
            lines.append(
                f"{position}. {product.name} ({product.category}) - "
                f"{money(float(product.revenue))} from {product.units_sold:,} units, "
                f"{product.revenue_share_percent:.1f}% share{growth}. "
                f"Stock on hand: {product.current_stock}."
            )
        context.add_detail("Top products:\n" + "\n".join(lines))
        context.data = {
            "products": [
                {
                    "product_id": product.product_id,
                    "name": product.name,
                    "revenue": float(product.revenue),
                    "units_sold": product.units_sold,
                    "current_stock": product.current_stock,
                    "growth_percent": product.growth_percent,
                }
                for product in products
            ]
        }

    def _worst_products(self, context, date_from, date_to, routing) -> None:
        products = self.analytics.product_performance(
            date_from, date_to, limit=5, ascending=True
        )
        context.add_source("sale_items joined to products")
        if not products:
            context.has_data = False
            context.summary = f"No products were sold in {context.period_label}."
            return

        context.summary = (
            f"These products generated the least revenue in {context.period_label}. "
            f"The weakest is '{products[0].name}' at "
            f"{money(float(products[0].revenue))}."
        )
        context.add_detail(
            "Lowest performing products:\n"
            + "\n".join(
                f"{position}. {product.name} ({product.category}) - "
                f"{money(float(product.revenue))} from {product.units_sold} units, "
                f"{product.current_stock} still in stock."
                for position, product in enumerate(products, start=1)
            )
        )
        context.data = {
            "products": [
                {
                    "product_id": product.product_id,
                    "name": product.name,
                    "revenue": float(product.revenue),
                    "units_sold": product.units_sold,
                    "current_stock": product.current_stock,
                }
                for product in products
            ]
        }

    def _categories(self, context, date_from, date_to, routing) -> None:
        categories = self.analytics.category_performance(date_from, date_to)
        context.add_source("sale_items joined to products, grouped by category")
        if not categories:
            context.has_data = False
            context.summary = f"No category activity in {context.period_label}."
            return

        best = categories[0]
        context.summary = (
            f"'{best.category}' is your strongest category in {context.period_label}, "
            f"contributing {money(float(best.revenue))} which is "
            f"{best.revenue_share_percent:.1f}% of revenue."
        )
        context.add_detail(
            "Category performance:\n"
            + "\n".join(
                f"- {row.category}: {money(float(row.revenue))} "
                f"({row.revenue_share_percent:.1f}% share, {row.units_sold:,} units"
                + (
                    f", {row.growth_percent:+.0f}% versus previous period)"
                    if row.growth_percent is not None
                    else ")"
                )
                for row in categories[:8]
            )
        )
        context.data = {
            "categories": [
                {
                    "category": row.category,
                    "revenue": float(row.revenue),
                    "share_percent": row.revenue_share_percent,
                    "growth_percent": row.growth_percent,
                }
                for row in categories
            ]
        }

    def _customers(self, context, date_from, date_to, routing) -> None:
        customers = self.analytics.top_customers(date_from, date_to, limit=5)
        context.add_source("sales joined to customers")
        if not customers:
            context.has_data = False
            context.summary = f"No customer purchases in {context.period_label}."
            return

        top = customers[0]
        context.summary = (
            f"Your highest spending customer in {context.period_label} is "
            f"{top.name} with {money(float(top.total_spent))} across "
            f"{top.total_orders} orders."
        )
        context.add_detail(
            "Top customers:\n"
            + "\n".join(
                f"{position}. {row.name} ({row.customer_code}"
                + (f", {row.city}" if row.city else "")
                + f") - {money(float(row.total_spent))} from {row.total_orders} orders, "
                f"average {money(float(row.average_order_value))}."
                for position, row in enumerate(customers, start=1)
            )
        )
        context.data = {
            "customers": [
                {
                    "customer_id": row.customer_id,
                    "name": row.name,
                    "total_spent": float(row.total_spent),
                    "total_orders": row.total_orders,
                }
                for row in customers
            ]
        }

    def _employees(self, context, date_from, date_to, routing) -> None:
        employees = self.analytics.employee_leaderboard(date_from, date_to, limit=5)
        context.add_source("sales joined to employees")
        if not employees:
            context.has_data = False
            context.summary = f"No employee sales recorded in {context.period_label}."
            return

        top = employees[0]
        context.summary = (
            f"{top.name} ({top.role}) leads the team in {context.period_label} with "
            f"{money(float(top.revenue))} from {top.transactions} sales."
        )
        context.add_detail(
            "Sales leaderboard:\n"
            + "\n".join(
                f"{position}. {row.name} ({row.role}) - {money(float(row.revenue))} "
                f"from {row.transactions} sales, average "
                f"{money(float(row.average_order_value))}."
                for position, row in enumerate(employees, start=1)
            )
        )

    def _demand_trend(self, context, date_from, date_to, routing) -> None:
        shifts = self.analytics.product_demand_shifts(window_days=30, limit=5)
        context.add_source("30 day versus prior 30 day unit comparison")

        rising, falling = shifts["rising_demand"], shifts["falling_demand"]
        if not rising and not falling:
            context.has_data = False
            context.summary = (
                "No product showed a demand change large enough to report over the "
                "last 30 days compared with the 30 days before."
            )
            return

        pieces = []
        if falling:
            pieces.append(f"{len(falling)} products have declining demand")
        if rising:
            pieces.append(f"{len(rising)} products have rising demand")
        context.summary = (
            "Comparing the last 30 days with the previous 30 days, "
            + " and ".join(pieces)
            + "."
        )

        if falling:
            context.add_detail(
                "Declining demand:\n"
                + "\n".join(
                    f"- {row['name']}: {row['current_units']} units versus "
                    f"{row['previous_units']} previously ({row['change_percent']:+.0f}%), "
                    f"{row['current_stock']} still in stock."
                    for row in falling
                )
            )
        if rising:
            context.add_detail(
                "Rising demand:\n"
                + "\n".join(
                    f"- {row['name']}: {row['current_units']} units versus "
                    f"{row['previous_units']} previously ({row['change_percent']:+.0f}%), "
                    f"{row['current_stock']} in stock."
                    for row in rising
                )
            )
        context.data = shifts

    def _sales_forecast(self, context, date_from, date_to, routing) -> None:
        from app.core.exceptions import ModelNotTrainedError
        from app.ml.predictor import PredictionService

        horizon = routing.horizon_days or settings_horizon()
        try:
            forecast = PredictionService(self.db).forecast_sales(horizon)
        except ModelNotTrainedError as exc:
            context.has_data = False
            context.summary = str(exc.message)
            context.add_fact(
                "A forecast requires the trained sales model. "
                "It can be trained from historical sales at any time."
            )
            return

        context.add_source(
            f"sales forecasting model ({forecast['model']['algorithm']}, trained "
            f"{forecast['model']['trained_at'][:10]})"
        )
        total = forecast["total_predicted_revenue"]
        change = forecast["change_vs_recent_percent"]
        context.summary = (
            f"Expected revenue over the next {horizon} days is about "
            f"{money(total)}, an average of "
            f"{money(forecast['daily_average_predicted'])} per day."
        )
        context.add_fact(f"Total forecast revenue: {money(total)}")
        context.add_fact(
            f"Recent actual daily average: {money(forecast['recent_daily_average'])}"
        )
        if change is not None:
            context.add_fact(
                f"That is {change:+.1f}% versus the recent daily average."
            )
        context.add_fact(
            f"Model accuracy on unseen data: average error "
            f"{money(forecast['model']['test_mae'])} per day "
            f"({forecast['model']['test_mape']}% MAPE)."
        )
        context.add_detail(
            "Daily forecast:\n"
            + "\n".join(
                f"- {row['date']}: {money(row['predicted_revenue'])}"
                for row in forecast["predictions"]
            )
        )
        context.data = forecast


def settings_horizon() -> int:
    from app.core.config import settings

    return settings.forecast_default_horizon
