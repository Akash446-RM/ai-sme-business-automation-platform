"""Inventory intelligence endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import Page, PageParams, page_params
from app.schemas.inventory import (
    InventoryOverview,
    InventoryTransactionDetail,
    InventoryValuation,
    MovementAnalysis,
    ReorderRecommendation,
    StockItem,
)
from app.services.forecast_service import build_inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/overview", response_model=InventoryOverview, summary="Stock health summary")
def overview(db: DbSession, _: CurrentUser) -> InventoryOverview:
    return build_inventory_service(db).overview()


@router.get("/stock", response_model=Page[StockItem], summary="Stock list with velocity")
def stock(
    db: DbSession,
    _: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    status_filter: Optional[str] = Query(
        None, pattern="^(healthy|low|out_of_stock|overstock)$", alias="status"
    ),
    category: Optional[str] = Query(None, max_length=80),
    search: Optional[str] = Query(None, max_length=100),
) -> Page[StockItem]:
    items, total = build_inventory_service(db).stock_items(
        params, status_filter=status_filter, category=category, search=search
    )
    return Page.create(items, total, params)


@router.get(
    "/recommendations",
    response_model=List[ReorderRecommendation],
    summary="Explainable reorder recommendations",
)
def recommendations(
    db: DbSession,
    _: CurrentUser,
    horizon_days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    only_actionable: bool = True,
) -> List[ReorderRecommendation]:
    return build_inventory_service(db).reorder_recommendations(
        horizon_days=horizon_days, limit=limit, only_actionable=only_actionable
    )


@router.get(
    "/recommendations/{product_id}",
    response_model=ReorderRecommendation,
    summary="Reorder recommendation for one product",
)
def recommendation_for_product(
    product_id: int,
    db: DbSession,
    _: CurrentUser,
    horizon_days: int = Query(7, ge=1, le=90),
) -> ReorderRecommendation:
    return build_inventory_service(db).recommendation_for(product_id, horizon_days)


@router.get(
    "/movement",
    response_model=MovementAnalysis,
    summary="Fast, slow and non moving products",
)
def movement(
    db: DbSession,
    _: CurrentUser,
    window_days: int = Query(30, ge=7, le=365),
    limit: int = Query(10, ge=1, le=50),
) -> MovementAnalysis:
    return build_inventory_service(db).movement_analysis(window_days, limit)


@router.get("/dead-stock", response_model=List[StockItem], summary="Capital stuck in dead stock")
def dead_stock(
    db: DbSession, _: CurrentUser, limit: int = Query(20, ge=1, le=100)
) -> List[StockItem]:
    return build_inventory_service(db).dead_stock(limit)


@router.get(
    "/valuation",
    response_model=List[InventoryValuation],
    summary="Inventory value by category",
)
def valuation(db: DbSession, _: CurrentUser) -> List[InventoryValuation]:
    return build_inventory_service(db).valuation()


@router.get(
    "/transactions",
    response_model=Page[InventoryTransactionDetail],
    summary="Stock movement ledger",
)
def transactions(
    db: DbSession,
    _: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    product_id: Optional[int] = Query(None, gt=0),
    transaction_type: Optional[str] = Query(
        None, pattern="^(sale|purchase|adjustment|return|initial|damage)$"
    ),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    reference: Optional[str] = Query(None, max_length=60),
) -> Page[InventoryTransactionDetail]:
    items, total = build_inventory_service(db).transactions(
        params,
        product_id=product_id,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        reference=reference,
    )
    return Page.create(items, total, params)
