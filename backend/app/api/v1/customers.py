"""Customer management endpoints."""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_manager
from app.core.pagination import Page, PageParams, page_params
from app.models.user import User
from app.schemas.common import Message
from app.schemas.customer import (
    CustomerCreate,
    CustomerDetail,
    CustomerRead,
    CustomerUpdate,
)
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])

ManagerDep = Annotated[User, Depends(require_manager)]


@router.get("", response_model=Page[CustomerRead], summary="List customers")
def list_customers(
    db: DbSession,
    _: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    search: Optional[str] = Query(None, max_length=100),
    city: Optional[str] = Query(None, max_length=80),
    is_active: Optional[bool] = None,
    sort_by: str = Query("name", pattern="^(name|customer_code|city|created_at)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
) -> Page[CustomerRead]:
    customers, total = CustomerService(db).list_customers(
        params,
        search=search,
        city=city,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page.create(
        [CustomerRead.model_validate(customer) for customer in customers], total, params
    )


@router.get("/cities", response_model=List[str], summary="Distinct customer cities")
def list_cities(db: DbSession, _: CurrentUser) -> List[str]:
    return CustomerService(db).cities()


@router.get(
    "/{customer_id}",
    response_model=CustomerDetail,
    summary="Customer profile with purchase behaviour",
)
def get_customer(customer_id: int, db: DbSession, _: CurrentUser) -> CustomerDetail:
    return CustomerService(db).detail(customer_id)


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer",
)
def create_customer(payload: CustomerCreate, db: DbSession, _: CurrentUser) -> CustomerRead:
    return CustomerRead.model_validate(CustomerService(db).create(payload))


@router.put("/{customer_id}", response_model=CustomerRead, summary="Update a customer")
def update_customer(
    customer_id: int, payload: CustomerUpdate, db: DbSession, _: CurrentUser
) -> CustomerRead:
    return CustomerRead.model_validate(CustomerService(db).update(customer_id, payload))


@router.post(
    "/{customer_id}/deactivate",
    response_model=CustomerRead,
    summary="Deactivate a customer",
)
def deactivate_customer(customer_id: int, db: DbSession, _: ManagerDep) -> CustomerRead:
    return CustomerRead.model_validate(CustomerService(db).deactivate(customer_id))


@router.delete("/{customer_id}", response_model=Message, summary="Delete a customer")
def delete_customer(customer_id: int, db: DbSession, _: ManagerDep) -> Message:
    CustomerService(db).delete(customer_id)
    return Message(message="Customer deleted successfully.")
