"""Data access for inventory transactions and stock movement analysis."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.repositories.base import BaseRepository


class InventoryRepository(BaseRepository[InventoryTransaction]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, InventoryTransaction)

    def build_query(
        self,
        *,
        product_id: Optional[int] = None,
        transaction_type: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        reference: Optional[str] = None,
    ) -> Select:
        statement = select(InventoryTransaction)
        if product_id:
            statement = statement.where(InventoryTransaction.product_id == product_id)
        if transaction_type:
            statement = statement.where(
                InventoryTransaction.transaction_type == transaction_type
            )
        if date_from:
            statement = statement.where(
                InventoryTransaction.created_at
                >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to:
            statement = statement.where(
                InventoryTransaction.created_at
                < datetime.combine(date_to + timedelta(days=1), datetime.min.time())
            )
        if reference:
            statement = statement.where(InventoryTransaction.reference == reference)
        return statement.order_by(
            InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc()
        )

    def product_history(self, product_id: int, limit: int = 50) -> List[InventoryTransaction]:
        return list(
            self.db.execute(
                select(InventoryTransaction)
                .where(InventoryTransaction.product_id == product_id)
                .order_by(InventoryTransaction.created_at.desc())
                .limit(limit)
            ).scalars()
        )

    # -- sales velocity ---------------------------------------------------
    def units_sold(
        self, product_id: int, *, since: datetime, until: Optional[datetime] = None
    ) -> int:
        """Total units of a product sold within a window."""
        statement = (
            select(func.coalesce(func.sum(SaleItem.quantity), 0))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(SaleItem.product_id == product_id, Sale.sale_date >= since)
        )
        if until:
            statement = statement.where(Sale.sale_date < until)
        return int(self.db.execute(statement).scalar_one() or 0)

    def units_sold_bulk(
        self, product_ids: List[int], *, since: datetime, until: Optional[datetime] = None
    ) -> dict[int, int]:
        """Units sold per product for many products in a single query."""
        if not product_ids:
            return {}
        statement = (
            select(SaleItem.product_id, func.coalesce(func.sum(SaleItem.quantity), 0))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(SaleItem.product_id.in_(product_ids), Sale.sale_date >= since)
        )
        if until:
            statement = statement.where(Sale.sale_date < until)
        rows = self.db.execute(statement.group_by(SaleItem.product_id)).all()
        return {int(row[0]): int(row[1] or 0) for row in rows}

    def daily_units_sold(self, product_id: int, *, since: datetime) -> List[tuple]:
        """Per-day unit sales for a product, used for velocity statistics."""
        return list(
            self.db.execute(
                select(
                    func.date(Sale.sale_date).label("day"),
                    func.coalesce(func.sum(SaleItem.quantity), 0),
                )
                .select_from(SaleItem)
                .join(Sale, SaleItem.sale_id == Sale.id)
                .where(SaleItem.product_id == product_id, Sale.sale_date >= since)
                .group_by(func.date(Sale.sale_date))
                .order_by(func.date(Sale.sale_date))
            ).all()
        )

    def last_sold_at(self, product_id: int) -> Optional[datetime]:
        return self.db.execute(
            select(func.max(Sale.sale_date))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(SaleItem.product_id == product_id)
        ).scalar_one_or_none()

    def never_sold_products(self, limit: int = 50) -> List[Product]:
        sold_subquery = select(SaleItem.product_id).distinct()
        return list(
            self.db.execute(
                select(Product)
                .where(Product.is_active.is_(True), Product.id.not_in(sold_subquery))
                .order_by(Product.stock.desc())
                .limit(limit)
            ).scalars()
        )

    def movement_ranking(
        self, *, since: datetime, limit: int = 20, ascending: bool = False
    ) -> List[tuple]:
        """Products ranked by units sold since a date."""
        order = func.sum(SaleItem.quantity).asc() if ascending else func.sum(SaleItem.quantity).desc()
        return list(
            self.db.execute(
                select(
                    Product.id,
                    Product.name,
                    Product.category,
                    Product.stock,
                    func.coalesce(func.sum(SaleItem.quantity), 0).label("units"),
                    func.coalesce(func.sum(SaleItem.line_total), 0).label("revenue"),
                )
                .select_from(SaleItem)
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Product, SaleItem.product_id == Product.id)
                .where(Sale.sale_date >= since)
                .group_by(Product.id, Product.name, Product.category, Product.stock)
                .order_by(order)
                .limit(limit)
            ).all()
        )
