"""Sale and sale item schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import PaymentMethod
from app.schemas.common import ORMModel

MAX_ITEMS_PER_SALE = 100


class SaleItemCreate(BaseModel):
    """One product line requested by the client."""

    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=10_000)
    unit_price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        decimal_places=2,
        description="Overrides the catalogue price when supplied",
    )
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class SaleCreate(BaseModel):
    """Request payload used to raise a new bill."""

    customer_id: Optional[int] = Field(default=None, gt=0)
    employee_id: Optional[int] = Field(default=None, gt=0)
    items: List[SaleItemCreate] = Field(min_length=1, max_length=MAX_ITEMS_PER_SALE)
    discount_amount: Decimal = Field(
        default=Decimal("0.00"), ge=0, decimal_places=2, description="Bill level discount"
    )
    gst_rate: Optional[Decimal] = Field(
        default=None, ge=0, le=100, description="Defaults to the configured GST rate"
    )
    payment_method: PaymentMethod = PaymentMethod.CASH
    notes: Optional[str] = Field(default=None, max_length=255)
    sale_date: Optional[datetime] = Field(
        default=None, description="Defaults to now; used for back-dated imports"
    )

    @field_validator("items")
    @classmethod
    def _unique_products(cls, items: List[SaleItemCreate]) -> List[SaleItemCreate]:
        product_ids = [item.product_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("each product may appear only once per sale")
        return items

    @model_validator(mode="after")
    def _no_future_dates(self) -> "SaleCreate":
        if self.sale_date and self.sale_date > datetime.now():
            raise ValueError("sale_date cannot be in the future")
        return self


class SaleItemRead(ORMModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal


class SaleRead(ORMModel):
    id: int
    bill_no: str
    customer_id: Optional[int]
    employee_id: Optional[int]
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    gst_rate: Decimal
    gst_amount: Decimal
    total_amount: Decimal
    payment_method: PaymentMethod
    notes: Optional[str]
    sale_date: datetime
    created_at: datetime


class SaleListItem(SaleRead):
    """Sale row enriched with display names for list screens."""

    customer_name: Optional[str] = None
    employee_name: Optional[str] = None
    item_count: int = 0


class SaleDetail(SaleRead):
    """Full bill including its line items."""

    items: List[SaleItemRead] = Field(default_factory=list)
    customer_name: Optional[str] = None
    employee_name: Optional[str] = None


class SaleCreatedResponse(BaseModel):
    """Result of a successful sale, including side effects."""

    sale: SaleDetail
    stock_updates: List["StockUpdateInfo"] = Field(default_factory=list)
    alerts_raised: List[str] = Field(default_factory=list)


class StockUpdateInfo(BaseModel):
    product_id: int
    product_name: str
    previous_stock: int
    new_stock: int
    below_reorder_level: bool


SaleCreatedResponse.model_rebuild()
