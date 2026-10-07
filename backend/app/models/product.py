"""Product catalogue model."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.inventory_transaction import InventoryTransaction
    from app.models.sale_item import SaleItem


class Product(Base, TimestampMixin):
    """An item the business buys, stocks and sells."""

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_category_active", "category", "is_active"),
        Index("ix_products_stock", "stock"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)

    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_stock_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    supplier: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    sale_items: Mapped[List["SaleItem"]] = relationship(back_populates="product")
    inventory_transactions: Mapped[List["InventoryTransaction"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    @property
    def margin_per_unit(self) -> Decimal:
        """Gross profit earned on a single unit."""
        return self.selling_price - self.cost_price

    @property
    def stock_value(self) -> Decimal:
        """Value of the units currently held, valued at cost."""
        return self.cost_price * self.stock

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Product {self.sku} {self.name!r} stock={self.stock}>"
