"""Immutable audit trail of every stock movement."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TransactionType

if TYPE_CHECKING:  # pragma: no cover
    from app.models.product import Product


class InventoryTransaction(Base):
    """One recorded change to a product's stock level.

    ``previous_stock`` and ``new_stock`` make the ledger self verifying: the
    stock level at any point in time can be reconstructed without replaying
    business logic.
    """

    __tablename__ = "inventory_transactions"
    __table_args__ = (
        Index("ix_inv_tx_product_date", "product_id", "created_at"),
        Index("ix_inv_tx_type_date", "transaction_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, native_enum=False, length=20), nullable=False
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Signed change: negative reduces stock"
    )
    previous_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    new_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )

    product: Mapped["Product"] = relationship(back_populates="inventory_transactions")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<InventoryTransaction product={self.product_id} "
            f"{self.transaction_type} qty={self.quantity}>"
        )
