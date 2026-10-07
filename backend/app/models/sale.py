"""Sale header: one completed business transaction."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PaymentMethod
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.customer import Customer
    from app.models.employee import Employee
    from app.models.sale_item import SaleItem


class Sale(Base, TimestampMixin):
    """A bill raised for one or more products.

    ``sale_date`` is the business timestamp used by every analytics and
    forecasting query, and is therefore indexed independently of ``created_at``.
    """

    __tablename__ = "sales"
    __table_args__ = (
        Index("ix_sales_date_customer", "sale_date", "customer_id"),
        Index("ix_sales_date_employee", "sale_date", "employee_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bill_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)

    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=20),
        nullable=False,
        default=PaymentMethod.CASH,
    )
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sale_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )

    customer: Mapped[Optional["Customer"]] = relationship(back_populates="sales")
    employee: Mapped[Optional["Employee"]] = relationship(back_populates="sales")
    items: Mapped[List["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Sale {self.bill_no} total={self.total_amount}>"
