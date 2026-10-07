"""Customer schemas."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel

PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{7,20}$")


class CustomerBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    city: Optional[str] = Field(default=None, max_length=80)
    address: Optional[str] = Field(default=None, max_length=255)

    @field_validator("name", "city", "address")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not PHONE_PATTERN.match(cleaned):
            raise ValueError("phone must contain 7-20 digits and may include + - ( ) spaces")
        return cleaned


class CustomerCreate(CustomerBase):
    customer_code: Optional[str] = Field(
        default=None, max_length=20, description="Auto-generated when omitted"
    )


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    city: Optional[str] = Field(default=None, max_length=80)
    address: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


class CustomerRead(ORMModel):
    id: int
    customer_code: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    city: Optional[str]
    address: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerPurchaseSummary(BaseModel):
    """Aggregated buying behaviour for a single customer."""

    customer_id: int
    customer_code: str
    name: str
    total_orders: int
    total_spent: Decimal
    average_order_value: Decimal
    first_purchase: Optional[datetime]
    last_purchase: Optional[datetime]
    days_since_last_purchase: Optional[int]
    favourite_category: Optional[str] = None


class CustomerDetail(CustomerRead):
    """Customer record enriched with purchase behaviour."""

    purchase_summary: Optional[CustomerPurchaseSummary] = None
    recent_bills: List[str] = Field(default_factory=list)
