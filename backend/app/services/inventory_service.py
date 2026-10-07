"""Inventory intelligence.

This service turns raw stock numbers into decisions. It combines current
stock, historical sales velocity, forecasted demand, reorder levels and safety
stock into explainable recommendations. Every recommendation carries the facts
that produced it so the UI and the AI layer can justify the advice.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams
from app.models.enums import MovementClass, StockStatus
from app.models.product import Product
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.inventory import (
    InventoryOverview,
    InventoryTransactionDetail,
    InventoryValuation,
    MovementAnalysis,
    MovementItem,
    ReorderRecommendation,
    StockItem,
)

logger = logging.getLogger(__name__)

VELOCITY_WINDOW_DAYS = 30
FAST_MOVER_DAILY_UNITS = 1.0
SLOW_MOVER_DAILY_UNITS = 0.1
DEAD_STOCK_DAYS = 90

# Demand forecasters injected by the forecasting layer.
# Single:  (product_id, horizon_days) -> (predicted_units, source_label)
# Bulk:    (product_ids, horizon_days) -> {product_id: (units, source_label)}
DemandForecaster = Callable[[int, int], Tuple[float, str]]
BulkDemandForecaster = Callable[[Sequence[int], int], Dict[int, Tuple[float, str]]]


class InventoryService:
    def __init__(
        self,
        db: Session,
        forecaster: Optional[DemandForecaster] = None,
        bulk_forecaster: Optional[BulkDemandForecaster] = None,
    ) -> None:
        self.db = db
        self.repo = InventoryRepository(db)
        self.product_repo = ProductRepository(db)
        self._forecaster = forecaster
        self._bulk_forecaster = bulk_forecaster
        # Populated before a batch run so each product reuses one shared forecast.
        self._forecast_cache: Dict[int, Tuple[float, str]] = {}

    # -- overview ---------------------------------------------------------
    def overview(self) -> InventoryOverview:
        """High level stock health counts computed with aggregate queries."""
        totals = self.db.execute(
            select(
                func.count(Product.id),
                func.coalesce(func.sum(Product.stock), 0),
                func.coalesce(func.sum(Product.stock * Product.cost_price), 0),
            ).where(Product.is_active.is_(True))
        ).one()

        out_of_stock = self.product_repo.count_out_of_stock()
        low_stock = self.product_repo.count_low_stock()
        overstock = int(
            self.db.execute(
                select(func.count(Product.id)).where(
                    Product.is_active.is_(True),
                    Product.max_stock_level.is_not(None),
                    Product.stock > Product.max_stock_level,
                )
            ).scalar_one()
        )
        total_products = int(totals[0])
        healthy = max(total_products - out_of_stock - low_stock - overstock, 0)

        return InventoryOverview(
            total_products=total_products,
            total_units=int(totals[1] or 0),
            total_stock_value=Decimal(str(totals[2] or 0)),
            healthy_count=healthy,
            low_stock_count=low_stock,
            out_of_stock_count=out_of_stock,
            overstock_count=overstock,
            dead_stock_count=len(self._dead_stock_products(limit=500)),
        )

    # -- stock listing ----------------------------------------------------
    def stock_items(
        self,
        params: PageParams,
        *,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[StockItem], int]:
        """Paginated stock list enriched with velocity and cover."""
        query = self.product_repo.build_query(
            search=search,
            category=category,
            is_active=True,
            low_stock_only=status_filter == "low",
            out_of_stock_only=status_filter == "out_of_stock",
            sort_by="stock",
            sort_dir="asc",
        )
        if status_filter == "overstock":
            query = query.where(
                Product.max_stock_level.is_not(None), Product.stock > Product.max_stock_level
            )
        elif status_filter == "healthy":
            query = query.where(Product.stock > Product.reorder_level)

        products, total = self.product_repo.paginate(query, params)
        return self._to_stock_items(products), total

    def _to_stock_items(self, products: List[Product]) -> List[StockItem]:
        if not products:
            return []
        since = datetime.now() - timedelta(days=VELOCITY_WINDOW_DAYS)
        product_ids = [product.id for product in products]
        sold_map = self.repo.units_sold_bulk(product_ids, since=since)

        items: List[StockItem] = []
        for product in products:
            units_sold = sold_map.get(product.id, 0)
            velocity = round(units_sold / VELOCITY_WINDOW_DAYS, 3)
            cover = round(product.stock / velocity, 1) if velocity > 0 else None
            items.append(
                StockItem(
                    product_id=product.id,
                    name=product.name,
                    sku=product.sku,
                    category=product.category,
                    stock=product.stock,
                    reorder_level=product.reorder_level,
                    stock_status=self.classify_stock(product),
                    stock_value=product.cost_price * product.stock,
                    units_sold_30d=units_sold,
                    daily_velocity=velocity,
                    days_of_cover=cover,
                    last_sold_at=None,
                    movement_class=self.classify_movement(velocity),
                )
            )
        return items

    # -- classification rules --------------------------------------------
    @staticmethod
    def classify_stock(product: Product) -> StockStatus:
        if product.stock <= 0:
            return StockStatus.OUT_OF_STOCK
        if product.stock <= product.reorder_level:
            return StockStatus.LOW
        if product.max_stock_level is not None and product.stock > product.max_stock_level:
            return StockStatus.OVERSTOCK
        return StockStatus.HEALTHY

    @staticmethod
    def classify_movement(daily_velocity: float) -> MovementClass:
        if daily_velocity <= 0:
            return MovementClass.DEAD
        if daily_velocity >= FAST_MOVER_DAILY_UNITS:
            return MovementClass.FAST
        if daily_velocity <= SLOW_MOVER_DAILY_UNITS:
            return MovementClass.SLOW
        return MovementClass.MEDIUM

    # -- recommendations --------------------------------------------------
    def recommendation_for(
        self, product_id: int, horizon_days: Optional[int] = None
    ) -> ReorderRecommendation:
        product = self.product_repo.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")
        return self._build_recommendation(product, horizon_days or settings.forecast_default_horizon)

    def reorder_recommendations(
        self,
        *,
        horizon_days: Optional[int] = None,
        limit: int = 50,
        only_actionable: bool = True,
    ) -> List[ReorderRecommendation]:
        """Recommendations for products that need attention, most urgent first."""
        horizon = horizon_days or settings.forecast_default_horizon
        candidates = self._recommendation_candidates(horizon)

        # One vectorised forecast for the whole batch instead of one call per
        # product: this is the difference between ~20 seconds and under a second.
        self._prime_forecasts([product.id for product in candidates], horizon)
        try:
            recommendations = [
                self._build_recommendation(product, horizon) for product in candidates
            ]
        finally:
            self._forecast_cache = {}
        if only_actionable:
            recommendations = [item for item in recommendations if item.recommended_quantity > 0]

        urgency_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "none": 4}
        recommendations.sort(
            key=lambda item: (urgency_rank.get(item.urgency, 5), -item.recommended_quantity)
        )
        return recommendations[:limit]

    def _recommendation_candidates(self, horizon: int) -> List[Product]:
        """Products worth evaluating: low stock, or selling faster than cover."""
        low_stock = self.product_repo.low_stock_products()
        low_ids = {product.id for product in low_stock}

        since = datetime.now() - timedelta(days=VELOCITY_WINDOW_DAYS)
        movers = self.repo.movement_ranking(since=since, limit=200)
        mover_ids = [int(row[0]) for row in movers if int(row[0]) not in low_ids]
        extra = self.product_repo.get_many(mover_ids)

        # Only keep movers whose stock is within roughly two horizons of cover.
        sold_map = self.repo.units_sold_bulk([p.id for p in extra], since=since)
        at_risk = []
        for product in extra:
            velocity = sold_map.get(product.id, 0) / VELOCITY_WINDOW_DAYS
            if velocity <= 0:
                continue
            if product.stock <= velocity * horizon * 2:
                at_risk.append(product)
        return low_stock + at_risk

    def _build_recommendation(
        self, product: Product, horizon_days: int
    ) -> ReorderRecommendation:
        """Core reorder calculation, fully explainable.

        recommended = max(0, forecast_demand + safety_stock - current_stock)
        safety_stock = z * sigma(daily demand) * sqrt(lead time)
        """
        # Window of whole days ending today (inclusive).
        today = datetime.now().date()
        window_start = today - timedelta(days=VELOCITY_WINDOW_DAYS - 1)
        since = datetime.combine(window_start, datetime.min.time())

        daily_rows = self.repo.daily_units_sold(product.id, since=since)
        daily_map = {str(row[0]): int(row[1] or 0) for row in daily_rows}

        # Fill non-selling days with zero so variability is measured honestly.
        series = [
            daily_map.get(str(window_start + timedelta(days=offset)), 0)
            for offset in range(VELOCITY_WINDOW_DAYS)
        ]
        units_sold = sum(series)
        velocity = units_sold / VELOCITY_WINDOW_DAYS
        std_dev = statistics.pstdev(series) if len(series) > 1 else 0.0

        forecast_demand, forecast_source = self._forecast_demand(
            product.id, horizon_days, velocity
        )

        lead_time = max(product.lead_time_days or settings.default_lead_time_days, 1)
        safety_stock = round(settings.service_level_z * std_dev * (lead_time**0.5), 2)

        required = forecast_demand + safety_stock
        recommended = max(0, int(round(required - product.stock)))

        cover = round(product.stock / velocity, 1) if velocity > 0 else None
        status = self.classify_stock(product)
        urgency = self._urgency(product, status, cover, horizon_days, recommended)

        reasons = self._reasons(
            product=product,
            status=status,
            velocity=velocity,
            units_sold=units_sold,
            forecast_demand=forecast_demand,
            safety_stock=safety_stock,
            cover=cover,
            horizon_days=horizon_days,
            recommended=recommended,
            forecast_source=forecast_source,
        )

        return ReorderRecommendation(
            product_id=product.id,
            name=product.name,
            sku=product.sku,
            category=product.category,
            current_stock=product.stock,
            reorder_level=product.reorder_level,
            daily_velocity=round(velocity, 3),
            forecast_horizon_days=horizon_days,
            forecast_demand=round(forecast_demand, 2),
            safety_stock=safety_stock,
            recommended_quantity=recommended,
            urgency=urgency,
            stock_status=status,
            days_of_cover=cover,
            estimated_cost=(product.cost_price * recommended),
            forecast_source=forecast_source,
            reasons=reasons,
            evidence={
                "current_stock": product.stock,
                "reorder_level": product.reorder_level,
                "units_sold_last_30_days": units_sold,
                "average_daily_demand": round(velocity, 3),
                "demand_std_dev": round(std_dev, 3),
                "lead_time_days": lead_time,
                "forecast_horizon_days": horizon_days,
                "forecast_demand": round(forecast_demand, 2),
                "safety_stock": safety_stock,
                "days_of_cover": cover,
                "formula": "recommended = max(0, forecast_demand + safety_stock - current_stock)",
            },
        )

    def _prime_forecasts(self, product_ids: List[int], horizon_days: int) -> None:
        """Pre-compute forecasts for a batch of products in one pass."""
        self._forecast_cache = {}
        if not product_ids or self._bulk_forecaster is None:
            return
        try:
            self._forecast_cache = self._bulk_forecaster(product_ids, horizon_days)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Bulk demand forecast failed, falling back per product: %s", exc)
            self._forecast_cache = {}

    def _forecast_demand(
        self, product_id: int, horizon_days: int, velocity: float
    ) -> Tuple[float, str]:
        """Use the ML forecaster when available, otherwise fall back to velocity."""
        cached = self._forecast_cache.get(product_id)
        if cached is not None:
            predicted, source = cached
            if predicted is not None and predicted >= 0:
                return float(predicted), source

        if self._forecaster is not None:
            try:
                predicted, source = self._forecaster(product_id, horizon_days)
                if predicted is not None and predicted >= 0:
                    return float(predicted), source
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Demand forecast failed for product %s: %s", product_id, exc)
        return velocity * horizon_days, "statistical_baseline"

    @staticmethod
    def _urgency(
        product: Product,
        status: StockStatus,
        cover: Optional[float],
        horizon_days: int,
        recommended: int,
    ) -> str:
        if recommended <= 0:
            return "none"
        if status == StockStatus.OUT_OF_STOCK:
            return "critical"
        if cover is not None and cover <= horizon_days / 2:
            return "critical"
        if status == StockStatus.LOW or (cover is not None and cover <= horizon_days):
            return "high"
        if cover is not None and cover <= horizon_days * 2:
            return "medium"
        return "low"

    @staticmethod
    def _reasons(
        *,
        product: Product,
        status: StockStatus,
        velocity: float,
        units_sold: int,
        forecast_demand: float,
        safety_stock: float,
        cover: Optional[float],
        horizon_days: int,
        recommended: int,
        forecast_source: str,
    ) -> List[str]:
        reasons: List[str] = []
        if status == StockStatus.OUT_OF_STOCK:
            reasons.append("The product is currently out of stock.")
        elif status == StockStatus.LOW:
            reasons.append(
                f"Current stock ({product.stock}) is at or below the reorder level "
                f"({product.reorder_level})."
            )
        else:
            reasons.append(f"Current stock is {product.stock} units.")

        if units_sold > 0:
            reasons.append(
                f"{units_sold} units sold in the last {VELOCITY_WINDOW_DAYS} days "
                f"(about {velocity:.2f} per day)."
            )
        else:
            reasons.append(f"No units were sold in the last {VELOCITY_WINDOW_DAYS} days.")

        label = (
            "the trained demand model"
            if forecast_source.startswith("ml")
            else "recent sales velocity"
        )
        reasons.append(
            f"Expected demand over the next {horizon_days} days is about "
            f"{forecast_demand:.0f} units, based on {label}."
        )

        if forecast_demand > product.stock:
            reasons.append(
                f"Forecast demand ({forecast_demand:.0f}) exceeds available stock "
                f"({product.stock}), so a stockout is likely."
            )
        if cover is not None:
            reasons.append(f"At the current rate, stock will last about {cover:.1f} days.")
        if safety_stock > 0:
            reasons.append(
                f"A safety buffer of {safety_stock:.0f} units covers demand variability "
                f"during the {product.lead_time_days}-day supplier lead time."
            )
        if recommended > 0:
            reasons.append(f"Recommended order quantity is {recommended} units.")
        return reasons

    # -- movement analysis ------------------------------------------------
    def movement_analysis(self, window_days: int = 30, limit: int = 10) -> MovementAnalysis:
        since = datetime.now() - timedelta(days=window_days)
        fast = self.repo.movement_ranking(since=since, limit=limit)
        slow = self.repo.movement_ranking(since=since, limit=limit, ascending=True)
        never = self.repo.never_sold_products(limit=limit)

        def to_items(rows) -> List[MovementItem]:
            return [
                MovementItem(
                    product_id=int(row[0]),
                    name=row[1],
                    category=row[2],
                    stock=int(row[3]),
                    units_sold=int(row[4] or 0),
                    revenue=Decimal(str(row[5] or 0)),
                )
                for row in rows
            ]

        return MovementAnalysis(
            window_days=window_days,
            fast_moving=to_items(fast),
            slow_moving=to_items(slow),
            never_sold=[
                MovementItem(
                    product_id=product.id,
                    name=product.name,
                    category=product.category,
                    stock=product.stock,
                    units_sold=0,
                    revenue=Decimal("0"),
                )
                for product in never
            ],
        )

    def _dead_stock_products(self, limit: int = 50) -> List[Product]:
        """Products holding stock with no sales in the dead-stock window."""
        from app.models.sale import Sale
        from app.models.sale_item import SaleItem

        since = datetime.now() - timedelta(days=DEAD_STOCK_DAYS)
        recently_sold = (
            select(SaleItem.product_id)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(Sale.sale_date >= since)
            .distinct()
        )
        return list(
            self.db.execute(
                select(Product)
                .where(
                    Product.is_active.is_(True),
                    Product.stock > 0,
                    Product.id.not_in(recently_sold),
                )
                .order_by((Product.stock * Product.cost_price).desc())
                .limit(limit)
            ).scalars()
        )

    def dead_stock(self, limit: int = 20) -> List[StockItem]:
        return self._to_stock_items(self._dead_stock_products(limit))

    # -- valuation and ledger --------------------------------------------
    def valuation(self) -> List[InventoryValuation]:
        rows = self.db.execute(
            select(
                Product.category,
                func.count(Product.id),
                func.coalesce(func.sum(Product.stock), 0),
                func.coalesce(func.sum(Product.stock * Product.cost_price), 0),
                func.coalesce(func.sum(Product.stock * Product.selling_price), 0),
            )
            .where(Product.is_active.is_(True))
            .group_by(Product.category)
            .order_by(func.sum(Product.stock * Product.cost_price).desc())
        ).all()
        return [
            InventoryValuation(
                category=row[0],
                product_count=int(row[1]),
                total_units=int(row[2] or 0),
                cost_value=Decimal(str(row[3] or 0)),
                retail_value=Decimal(str(row[4] or 0)),
                potential_margin=Decimal(str((row[4] or 0) - (row[3] or 0))),
            )
            for row in rows
        ]

    def transactions(
        self, params: PageParams, **filters
    ) -> Tuple[List[InventoryTransactionDetail], int]:
        statement = self.repo.build_query(**filters)
        rows, total = self.repo.paginate(statement, params)
        product_map: Dict[int, Product] = {
            product.id: product
            for product in self.product_repo.get_many([row.product_id for row in rows])
        }
        items = []
        for row in rows:
            detail = InventoryTransactionDetail.model_validate(row)
            product = product_map.get(row.product_id)
            if product:
                detail.product_name = product.name
                detail.product_sku = product.sku
            items.append(detail)
        return items, total
