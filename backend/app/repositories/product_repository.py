"""Data access for products."""

from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories.base import BaseRepository

SORTABLE_FIELDS = {
    "name": Product.name,
    "category": Product.category,
    "sku": Product.sku,
    "stock": Product.stock,
    "cost_price": Product.cost_price,
    "selling_price": Product.selling_price,
    "created_at": Product.created_at,
    "updated_at": Product.updated_at,
}


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Product)

    def get_by_sku(self, sku: str) -> Optional[Product]:
        return self.db.execute(
            select(Product).where(Product.sku == sku.strip().upper())
        ).scalar_one_or_none()

    def get_by_barcode(self, barcode: str) -> Optional[Product]:
        return self.db.execute(
            select(Product).where(Product.barcode == barcode.strip().upper())
        ).scalar_one_or_none()

    def get_by_name(self, name: str) -> Optional[Product]:
        """Case-insensitive exact name lookup (used by the AI layer)."""
        return self.db.execute(
            select(Product).where(func.lower(Product.name) == name.strip().lower())
        ).scalars().first()

    def search_by_name(self, term: str, limit: int = 10) -> List[Product]:
        pattern = f"%{term.strip()}%"
        return list(
            self.db.execute(
                select(Product)
                .where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
                .order_by(Product.name)
                .limit(limit)
            ).scalars()
        )

    def build_query(
        self,
        *,
        search: Optional[str] = None,
        category: Optional[str] = None,
        supplier: Optional[str] = None,
        is_active: Optional[bool] = None,
        low_stock_only: bool = False,
        out_of_stock_only: bool = False,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
    ) -> Select:
        """Compose a filtered, sorted product query."""
        statement = select(Product)

        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Product.name.ilike(pattern),
                    Product.sku.ilike(pattern),
                    Product.barcode.ilike(pattern),
                    Product.category.ilike(pattern),
                )
            )
        if category:
            statement = statement.where(Product.category == category)
        if supplier:
            statement = statement.where(Product.supplier == supplier)
        if is_active is not None:
            statement = statement.where(Product.is_active.is_(is_active))
        if out_of_stock_only:
            statement = statement.where(Product.stock <= 0)
        elif low_stock_only:
            statement = statement.where(
                Product.stock > 0, Product.stock <= Product.reorder_level
            )
        if min_price is not None:
            statement = statement.where(Product.selling_price >= min_price)
        if max_price is not None:
            statement = statement.where(Product.selling_price <= max_price)

        column = SORTABLE_FIELDS.get(sort_by, Product.name)
        statement = statement.order_by(
            column.desc() if sort_dir.lower() == "desc" else column.asc(), Product.id
        )
        return statement

    def lock_for_update(self, product_ids: Sequence[int]) -> List[Product]:
        """Fetch products with a row lock, ordered by id to avoid deadlocks.

        SQLite ignores FOR UPDATE, which is acceptable because tests run
        single threaded; MySQL applies a real lock.
        """
        if not product_ids:
            return []
        ordered_ids = sorted(set(product_ids))
        statement = (
            select(Product).where(Product.id.in_(ordered_ids)).order_by(Product.id)
        )
        if self.db.bind is not None and self.db.bind.dialect.name != "sqlite":
            statement = statement.with_for_update()
        return list(self.db.execute(statement).scalars())

    def categories(self) -> List[str]:
        return [
            row[0]
            for row in self.db.execute(
                select(Product.category).distinct().order_by(Product.category)
            ).all()
        ]

    def suppliers(self) -> List[str]:
        return [
            row[0]
            for row in self.db.execute(
                select(Product.supplier)
                .where(Product.supplier.is_not(None))
                .distinct()
                .order_by(Product.supplier)
            ).all()
        ]

    def category_breakdown(self) -> List[tuple]:
        return list(
            self.db.execute(
                select(
                    Product.category,
                    func.count(Product.id),
                    func.coalesce(func.sum(Product.stock), 0),
                    func.coalesce(func.sum(Product.stock * Product.cost_price), 0),
                )
                .where(Product.is_active.is_(True))
                .group_by(Product.category)
                .order_by(Product.category)
            ).all()
        )

    def count_active(self) -> int:
        return int(
            self.db.execute(
                select(func.count(Product.id)).where(Product.is_active.is_(True))
            ).scalar_one()
        )

    def count_low_stock(self) -> int:
        return int(
            self.db.execute(
                select(func.count(Product.id)).where(
                    Product.is_active.is_(True),
                    Product.stock > 0,
                    Product.stock <= Product.reorder_level,
                )
            ).scalar_one()
        )

    def count_out_of_stock(self) -> int:
        return int(
            self.db.execute(
                select(func.count(Product.id)).where(
                    Product.is_active.is_(True), Product.stock <= 0
                )
            ).scalar_one()
        )

    def total_stock_value(self) -> float:
        value = self.db.execute(
            select(func.coalesce(func.sum(Product.stock * Product.cost_price), 0)).where(
                Product.is_active.is_(True)
            )
        ).scalar_one()
        return float(value or 0)

    def low_stock_products(self, limit: Optional[int] = None) -> List[Product]:
        statement = (
            select(Product)
            .where(
                Product.is_active.is_(True),
                Product.stock <= Product.reorder_level,
            )
            .order_by((Product.stock - Product.reorder_level).asc(), Product.name)
        )
        if limit:
            statement = statement.limit(limit)
        return list(self.db.execute(statement).scalars())
