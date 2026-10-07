"""Product schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.models.enums import StockStatus
from app.schemas.common import ORMModel

MONEY = Field(ge=0, decimal_places=2, max_digits=12)


class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=80)
    sku: str = Field(min_length=2, max_length=50)
    barcode: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=400)
    cost_price: Decimal = MONEY
    selling_price: Decimal = MONEY
    reorder_level: int = Field(default=10, ge=0, le=100_000)
    max_stock_level: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    supplier: Optional[str] = Field(default=None, max_length=120)
    lead_time_days: int = Field(default=5, ge=0, le=365)

    @field_validator("name", "category", "supplier")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if isinstance(value, str) else value

    @field_validator("sku", "barcode")
    @classmethod
    def _upper_strip(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_pricing(self) -> "ProductBase":
        if self.selling_price < self.cost_price:
            raise ValueError("selling_price cannot be lower than cost_price")
        if self.max_stock_level is not None and self.max_stock_level < self.reorder_level:
            raise ValueError("max_stock_level cannot be lower than reorder_level")
        return self


class ProductCreate(ProductBase):
    stock: int = Field(default=0, ge=0, le=1_000_000)


class ProductUpdate(BaseModel):
    """Partial update; every field is optional."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    category: Optional[str] = Field(default=None, min_length=2, max_length=80)
    barcode: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=400)
    cost_price: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    selling_price: Optional[Decimal] = Field(default=None, ge=0, decimal_places=2)
    reorder_level: Optional[int] = Field(default=None, ge=0, le=100_000)
    max_stock_level: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    supplier: Optional[str] = Field(default=None, max_length=120)
    lead_time_days: Optional[int] = Field(default=None, ge=0, le=365)
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def _check_pricing(self) -> "ProductUpdate":
        if (
            self.cost_price is not None
            and self.selling_price is not None
            and self.selling_price < self.cost_price
        ):
            raise ValueError("selling_price cannot be lower than cost_price")
        return self


class ProductRead(ORMModel):
    id: int
    name: str
    category: str
    sku: str
    barcode: Optional[str]
    description: Optional[str]
    cost_price: Decimal
    selling_price: Decimal
    stock: int
    reorder_level: int
    max_stock_level: Optional[int]
    supplier: Optional[str]
    lead_time_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def margin_per_unit(self) -> Decimal:
        return self.selling_price - self.cost_price

    @computed_field  # type: ignore[prop-decorator]
    @property
    def margin_percent(self) -> float:
        if self.selling_price == 0:
            return 0.0
        return round(float((self.selling_price - self.cost_price) / self.selling_price) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stock_value(self) -> Decimal:
        return self.cost_price * self.stock

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stock_status(self) -> StockStatus:
        if self.stock <= 0:
            return StockStatus.OUT_OF_STOCK
        if self.stock <= self.reorder_level:
            return StockStatus.LOW
        if self.max_stock_level is not None and self.stock > self.max_stock_level:
            return StockStatus.OVERSTOCK
        return StockStatus.HEALTHY


class ProductSummary(ORMModel):
    """Lightweight product representation for embedding in other payloads."""

    id: int
    name: str
    sku: str
    category: str
    selling_price: Decimal
    stock: int


class StockAdjustment(BaseModel):
    """Manual stock correction request."""

    quantity: int = Field(description="Signed change; negative reduces stock")
    reason: str = Field(min_length=3, max_length=255)

    @field_validator("quantity")
    @classmethod
    def _non_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("quantity must not be zero")
        return value


class CategoryInfo(BaseModel):
    category: str
    product_count: int
    total_stock: int
    stock_value: Decimal
