"""Product catalogue endpoints."""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_manager
from app.core.pagination import Page, PageParams, page_params
from app.models.user import User
from app.schemas.common import Message
from app.schemas.product import (
    CategoryInfo,
    ProductCreate,
    ProductRead,
    ProductSummary,
    ProductUpdate,
    StockAdjustment,
)
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])

ManagerDep = Annotated[User, Depends(require_manager)]


@router.get("", response_model=Page[ProductRead], summary="List products")
def list_products(
    db: DbSession,
    _: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    search: Optional[str] = Query(None, max_length=100),
    category: Optional[str] = Query(None, max_length=80),
    supplier: Optional[str] = Query(None, max_length=120),
    is_active: Optional[bool] = None,
    low_stock_only: bool = False,
    out_of_stock_only: bool = False,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    sort_by: str = Query("name", pattern="^(name|category|sku|stock|cost_price|selling_price|created_at|updated_at)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
) -> Page[ProductRead]:
    products, total = ProductService(db).list_products(
        params,
        search=search,
        category=category,
        supplier=supplier,
        is_active=is_active,
        low_stock_only=low_stock_only,
        out_of_stock_only=out_of_stock_only,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page.create(
        [ProductRead.model_validate(product) for product in products], total, params
    )


@router.get("/categories", response_model=List[str], summary="Distinct categories")
def list_categories(db: DbSession, _: CurrentUser) -> List[str]:
    return ProductService(db).categories()


@router.get("/suppliers", response_model=List[str], summary="Distinct suppliers")
def list_suppliers(db: DbSession, _: CurrentUser) -> List[str]:
    return ProductService(db).suppliers()


@router.get(
    "/category-breakdown",
    response_model=List[CategoryInfo],
    summary="Product count and stock value per category",
)
def category_breakdown(db: DbSession, _: CurrentUser) -> List[CategoryInfo]:
    return ProductService(db).category_breakdown()


@router.get(
    "/search",
    response_model=List[ProductSummary],
    summary="Quick product lookup for billing screens",
)
def search_products(
    db: DbSession,
    _: CurrentUser,
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=50),
) -> List[ProductSummary]:
    return [
        ProductSummary.model_validate(product)
        for product in ProductService(db).search(q, limit)
    ]


@router.get("/{product_id}", response_model=ProductRead, summary="Get one product")
def get_product(product_id: int, db: DbSession, _: CurrentUser) -> ProductRead:
    return ProductRead.model_validate(ProductService(db).get(product_id))


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product",
)
def create_product(
    payload: ProductCreate, db: DbSession, current_user: ManagerDep
) -> ProductRead:
    product = ProductService(db).create(payload, user_id=current_user.id)
    return ProductRead.model_validate(product)


@router.put("/{product_id}", response_model=ProductRead, summary="Update a product")
def update_product(
    product_id: int, payload: ProductUpdate, db: DbSession, _: ManagerDep
) -> ProductRead:
    return ProductRead.model_validate(ProductService(db).update(product_id, payload))


@router.post(
    "/{product_id}/adjust-stock",
    response_model=ProductRead,
    summary="Record a manual stock correction",
)
def adjust_stock(
    product_id: int,
    payload: StockAdjustment,
    db: DbSession,
    current_user: ManagerDep,
) -> ProductRead:
    product = ProductService(db).adjust_stock(product_id, payload, user_id=current_user.id)
    return ProductRead.model_validate(product)


@router.post(
    "/{product_id}/deactivate",
    response_model=ProductRead,
    summary="Soft delete a product",
)
def deactivate_product(product_id: int, db: DbSession, _: ManagerDep) -> ProductRead:
    return ProductRead.model_validate(ProductService(db).deactivate(product_id))


@router.delete("/{product_id}", response_model=Message, summary="Delete a product")
def delete_product(product_id: int, db: DbSession, _: ManagerDep) -> Message:
    ProductService(db).delete(product_id)
    return Message(message="Product deleted successfully.")
