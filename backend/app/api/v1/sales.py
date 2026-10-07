"""Sales endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_manager
from app.core.pagination import Page, PageParams, page_params
from app.models.user import User
from app.schemas.common import Message
from app.schemas.sale import SaleCreate, SaleCreatedResponse, SaleDetail, SaleListItem
from app.services.sales_service import SalesService

router = APIRouter(prefix="/sales", tags=["sales"])

ManagerDep = Annotated[User, Depends(require_manager)]


@router.get("", response_model=Page[SaleListItem], summary="List sales")
def list_sales(
    db: DbSession,
    _: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    search: Optional[str] = Query(None, max_length=50, description="Bill number"),
    customer_id: Optional[int] = Query(None, gt=0),
    employee_id: Optional[int] = Query(None, gt=0),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    payment_method: Optional[str] = Query(None, pattern="^(cash|card|upi|credit)$"),
    sort_by: str = Query("sale_date", pattern="^(sale_date|bill_no|total_amount|created_at)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> Page[SaleListItem]:
    items, total = SalesService(db).list_sales(
        params,
        search=search,
        customer_id=customer_id,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        payment_method=payment_method,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page.create(items, total, params)


@router.get("/recent", response_model=List[SaleListItem], summary="Most recent sales")
def recent_sales(
    db: DbSession, _: CurrentUser, limit: int = Query(10, ge=1, le=50)
) -> List[SaleListItem]:
    return SalesService(db).recent(limit)


@router.get("/by-bill/{bill_no}", response_model=SaleDetail, summary="Look up a bill")
def get_sale_by_bill(bill_no: str, db: DbSession, _: CurrentUser) -> SaleDetail:
    return SalesService(db).get_by_bill_no(bill_no)


@router.get("/{sale_id}", response_model=SaleDetail, summary="Get a sale with line items")
def get_sale(sale_id: int, db: DbSession, _: CurrentUser) -> SaleDetail:
    return SalesService(db).get_detail(sale_id)


@router.post(
    "",
    response_model=SaleCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a sale (updates stock and the inventory ledger)",
)
def create_sale(
    payload: SaleCreate, db: DbSession, current_user: CurrentUser
) -> SaleCreatedResponse:
    return SalesService(db).create_sale(payload, user_id=current_user.id)


@router.delete(
    "/{sale_id}",
    response_model=Message,
    summary="Void a sale and restore stock (manager only)",
)
def void_sale(sale_id: int, db: DbSession, current_user: ManagerDep) -> Message:
    SalesService(db).void_sale(sale_id, user_id=current_user.id)
    return Message(message="Sale voided and stock restored.")
