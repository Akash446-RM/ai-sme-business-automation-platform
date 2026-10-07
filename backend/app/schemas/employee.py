"""Employee schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.customer import PHONE_PATTERN


class EmployeeBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(min_length=2, max_length=60)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(default=None, max_length=60)
    hired_on: Optional[date] = None

    @field_validator("name", "role", "department")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        cleaned = value.strip()
        if not PHONE_PATTERN.match(cleaned):
            raise ValueError("phone must contain 7-20 digits and may include + - ( ) spaces")
        return cleaned

    @field_validator("hired_on")
    @classmethod
    def _not_future(cls, value: Optional[date]) -> Optional[date]:
        if value and value > date.today():
            raise ValueError("hired_on cannot be in the future")
        return value


class EmployeeCreate(EmployeeBase):
    employee_code: Optional[str] = Field(
        default=None, max_length=20, description="Auto-generated when omitted"
    )


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    role: Optional[str] = Field(default=None, min_length=2, max_length=60)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(default=None, max_length=60)
    hired_on: Optional[date] = None
    is_active: Optional[bool] = None


class EmployeeRead(ORMModel):
    id: int
    employee_code: str
    name: str
    role: str
    phone: Optional[str]
    email: Optional[str]
    department: Optional[str]
    hired_on: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EmployeePerformance(BaseModel):
    """Sales performance attributed to an employee."""

    employee_id: int
    employee_code: str
    name: str
    role: str
    total_sales: int
    total_revenue: Decimal
    average_order_value: Decimal
    last_sale_at: Optional[datetime]
