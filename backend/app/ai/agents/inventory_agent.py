"""Inventory agent.

Answers stock, restocking, stockout risk and demand forecast questions using
the inventory intelligence service. Because that service already produces an
explainable recommendation with reasons and evidence, this agent's job is to
retrieve the right recommendation and pass those reasons through unchanged.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.ai.context import BusinessContext, money
from app.ai.router import Intent, RoutingResult
from app.core.config import settings
from app.core.pagination import PageParams
from app.repositories.product_repository import ProductRepository
from app.services.forecast_service import build_inventory_service

logger = logging.getLogger(__name__)


class InventoryAgent:
    """Retrieves stock facts and explainable reorder advice."""

    name = "inventory_agent"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = build_inventory_service(db)
        self.product_repo = ProductRepository(db)

    def handle(self, routing: RoutingResult, question: str) -> BusinessContext:
        context = BusinessContext(intent=str(routing.intent), agent=self.name)
        horizon = routing.horizon_days or settings.forecast_default_horizon

        handlers = {
            Intent.STOCK_STATUS: self._stock_status,
            Intent.REORDER: self._reorder,
            Intent.STOCKOUT_RISK: self._stockout_risk,
            Intent.DEMAND_FORECAST: self._demand_forecast,
            Intent.PRODUCT_EXPLANATION: self._explain,
            Intent.DEAD_STOCK: self._dead_stock,
        }
        handler = handlers.get(routing.intent, self._stock_status)
        handler(context, routing, horizon)
        return context

    # -- product resolution ------------------------------------------------
    def _resolve_product(self, hint: Optional[str]):
        """Find the product a question refers to, if any."""
        if not hint:
            return None
        exact = self.product_repo.get_by_name(hint)
        if exact:
            return exact
        matches = self.product_repo.search_by_name(hint, limit=1)
        return matches[0] if matches else None

    # -- handlers ----------------------------------------------------------
    def _stock_status(self, context, routing, horizon) -> None:
        product = self._resolve_product(routing.product_hint)
        context.add_source("products table")

        if product is not None:
            recommendation = self.inventory.recommendation_for(product.id, horizon)
            context.summary = (
                f"'{product.name}' currently has {product.stock} units in stock "
                f"against a reorder level of {product.reorder_level}."
            )
            context.add_fact(f"Stock on hand: {product.stock} units")
            context.add_fact(f"Reorder level: {product.reorder_level} units")
            context.add_fact(f"Status: {str(recommendation.stock_status).replace('_', ' ')}")
            if recommendation.days_of_cover is not None:
                context.add_fact(
                    f"At the current sales rate this lasts about "
                    f"{recommendation.days_of_cover:.1f} days."
                )
            context.data = {"product": recommendation.model_dump(mode="json")}
            return

        overview = self.inventory.overview()
        context.summary = (
            f"You have {overview.total_products} active products holding "
            f"{overview.total_units:,} units worth "
            f"{money(float(overview.total_stock_value))}."
        )
        context.add_fact(f"Healthy stock: {overview.healthy_count} products")
        context.add_fact(f"Low stock: {overview.low_stock_count} products")
        context.add_fact(f"Out of stock: {overview.out_of_stock_count} products")
        context.add_fact(f"Overstocked: {overview.overstock_count} products")
        context.add_fact(
            f"No sales in 90 days: {overview.dead_stock_count} products"
        )

        params = PageParams(page=1, page_size=8)
        low_items, _ = self.inventory.stock_items(params, status_filter="low")
        if low_items:
            context.add_detail(
                "Products at or below their reorder level:\n"
                + "\n".join(
                    f"- {item.name}: {item.stock} units (reorder level "
                    f"{item.reorder_level}, sold {item.units_sold_30d} in 30 days)"
                    for item in low_items
                )
            )
        context.data = {"overview": overview.model_dump(mode="json")}

    def _reorder(self, context, routing, horizon) -> None:
        product = self._resolve_product(routing.product_hint)
        context.add_source("inventory recommendation engine")

        if product is not None:
            self._explain(context, routing, horizon)
            return

        recommendations = self.inventory.reorder_recommendations(
            horizon_days=horizon, limit=8
        )
        if not recommendations:
            context.summary = (
                "Nothing needs reordering right now. Every product has enough stock "
                f"to cover its forecast demand for the next {horizon} days."
            )
            context.add_fact("Products requiring a reorder: 0")
            return

        urgent = [item for item in recommendations if item.urgency in {"critical", "high"}]
        total_cost = sum(float(item.estimated_cost) for item in recommendations)

        context.summary = (
            f"{len(recommendations)} products need reordering to cover demand for the "
            f"next {horizon} days, {len(urgent)} of them urgently. "
            f"The estimated purchase cost is {money(total_cost)}."
        )
        context.add_fact(f"Products to reorder: {len(recommendations)}")
        context.add_fact(f"Urgent (critical or high): {len(urgent)}")
        context.add_fact(f"Estimated total cost: {money(total_cost)}")

        context.add_detail(
            "Recommended purchase list:\n"
            + "\n".join(
                f"- {item.name} ({item.sku}): order {item.recommended_quantity} units. "
                f"Stock {item.current_stock}, forecast demand "
                f"{item.forecast_demand:.0f} over {horizon} days, urgency "
                f"{item.urgency}. Estimated cost {money(float(item.estimated_cost))}."
                for item in recommendations
            )
        )
        sources = {item.forecast_source for item in recommendations}
        if "ml_demand_model" in sources:
            context.add_source("trained demand forecasting model")
        context.data = {
            "recommendations": [
                item.model_dump(mode="json") for item in recommendations
            ],
            "horizon_days": horizon,
        }

    def _stockout_risk(self, context, routing, horizon) -> None:
        recommendations = self.inventory.reorder_recommendations(
            horizon_days=horizon, limit=20
        )
        at_risk = [
            item
            for item in recommendations
            if item.forecast_demand > item.current_stock
        ]
        context.add_source("inventory recommendation engine")

        if not at_risk:
            context.summary = (
                f"No product is expected to run out within the next {horizon} days "
                f"based on current stock and forecast demand."
            )
            context.add_fact("Products at risk of stockout: 0")
            return

        context.summary = (
            f"{len(at_risk)} products are forecast to run out within the next "
            f"{horizon} days because expected demand exceeds available stock."
        )
        context.add_fact(f"Products at risk: {len(at_risk)}")
        context.add_detail(
            "Stockout risk:\n"
            + "\n".join(
                f"- {item.name}: {item.current_stock} units in stock versus forecast "
                f"demand of {item.forecast_demand:.0f} units over {horizon} days. "
                + (
                    f"Cover is about {item.days_of_cover:.1f} days. "
                    if item.days_of_cover is not None
                    else ""
                )
                + f"Reorder {item.recommended_quantity} units."
                for item in at_risk[:8]
            )
        )
        context.data = {"at_risk": [item.model_dump(mode="json") for item in at_risk]}

    def _demand_forecast(self, context, routing, horizon) -> None:
        from app.core.exceptions import ModelNotTrainedError, NotFoundError
        from app.ml.predictor import PredictionService

        product = self._resolve_product(routing.product_hint)
        if product is None:
            # No specific product mentioned: summarise where demand exceeds stock.
            self._stockout_risk(context, routing, horizon)
            return

        try:
            forecast = PredictionService(self.db).forecast_demand(product.id, horizon)
        except (ModelNotTrainedError, NotFoundError):
            recommendation = self.inventory.recommendation_for(product.id, horizon)
            context.add_source("recent sales velocity (model based forecast unavailable)")
            context.summary = (
                f"Based on recent sales, '{product.name}' is expected to sell about "
                f"{recommendation.forecast_demand:.0f} units over the next "
                f"{horizon} days. Current stock is {product.stock} units."
            )
            for reason in recommendation.reasons:
                context.add_fact(reason)
            context.data = {"recommendation": recommendation.model_dump(mode="json")}
            return

        context.add_source(
            f"demand forecasting model ({forecast['model']['algorithm']})"
        )
        total = forecast["total_predicted_units"]
        context.summary = (
            f"'{product.name}' is forecast to sell about {total:.0f} units over the "
            f"next {horizon} days. Current stock is {product.stock} units."
        )
        context.add_fact(f"Forecast demand: {total:.0f} units over {horizon} days")
        context.add_fact(f"Current stock: {product.stock} units")
        context.add_fact(
            f"Recent average: {forecast['recent_daily_average']:.2f} units per day"
        )
        context.add_fact(
            f"Expected stock after {horizon} days: "
            f"{forecast['expected_stock_after_horizon']:.0f} units"
        )
        if forecast["stockout_expected"]:
            context.add_fact(
                "Forecast demand exceeds current stock, so a stockout is expected."
            )
        context.data = forecast

    def _explain(self, context, routing, horizon) -> None:
        """Explain a recommendation using the engine's own reasons."""
        product = self._resolve_product(routing.product_hint)
        context.add_source("inventory recommendation engine")

        if product is None:
            context.has_data = False
            context.summary = (
                "I could not tell which product you meant. Please include the product "
                "name, for example: why should I reorder 'Wireless Mouse'?"
            )
            return

        recommendation = self.inventory.recommendation_for(product.id, horizon)
        if recommendation.recommended_quantity <= 0:
            context.summary = (
                f"'{product.name}' does not need reordering right now. It has "
                f"{recommendation.current_stock} units in stock against forecast "
                f"demand of {recommendation.forecast_demand:.0f} units over the next "
                f"{horizon} days."
            )
        else:
            context.summary = (
                f"'{product.name}' should be reordered with about "
                f"{recommendation.recommended_quantity} units. Here is why:"
            )

        for reason in recommendation.reasons:
            context.add_fact(reason)

        evidence = recommendation.evidence
        context.add_detail(
            "Calculation:\n"
            f"- Formula: {evidence['formula']}\n"
            f"- Forecast demand ({horizon} days): {evidence['forecast_demand']}\n"
            f"- Safety stock: {evidence['safety_stock']} "
            f"(covers a {evidence['lead_time_days']} day lead time)\n"
            f"- Current stock: {evidence['current_stock']}\n"
            f"- Recommended quantity: {recommendation.recommended_quantity}"
        )
        if recommendation.forecast_source == "ml_demand_model":
            context.add_source("trained demand forecasting model")
        context.data = {"recommendation": recommendation.model_dump(mode="json")}

    def _dead_stock(self, context, routing, horizon) -> None:
        items = self.inventory.dead_stock(limit=8)
        context.add_source("products with no sales in the last 90 days")

        if not items:
            context.summary = "Every product in stock has sold at least once in the last 90 days."
            context.add_fact("Dead stock products: 0")
            return

        total_value = sum(float(item.stock_value) for item in items)
        context.summary = (
            f"{len(items)} products have not sold in 90 days and are holding "
            f"{money(total_value)} of stock."
        )
        context.add_fact(f"Dead stock products listed: {len(items)}")
        context.add_fact(f"Capital tied up: {money(total_value)}")
        context.add_detail(
            "Products with no recent sales:\n"
            + "\n".join(
                f"- {item.name} ({item.category}): {item.stock} units worth "
                f"{money(float(item.stock_value))}"
                for item in items
            )
        )
        context.data = {"dead_stock": [item.model_dump(mode="json") for item in items]}
