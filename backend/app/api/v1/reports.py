"""Business report endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.report import (
    BusinessSummaryReport,
    CustomerReport,
    InventoryReport,
    ProductReport,
    RevenueReport,
    SalesReport,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/sales", response_model=SalesReport, summary="Sales report")
def sales_report(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> SalesReport:
    return ReportService(db).sales_report(date_from, date_to)


@router.get("/revenue", response_model=RevenueReport, summary="Revenue report")
def revenue_report(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> RevenueReport:
    return ReportService(db).revenue_report(date_from, date_to)


@router.get("/inventory", response_model=InventoryReport, summary="Inventory report")
def inventory_report(
    db: DbSession, _: CurrentUser, horizon_days: int = Query(7, ge=1, le=90)
) -> InventoryReport:
    return ReportService(db).inventory_report(horizon_days)


@router.get("/products", response_model=ProductReport, summary="Product performance report")
def product_report(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(15, ge=1, le=100),
) -> ProductReport:
    return ReportService(db).product_report(date_from, date_to, limit)


@router.get("/customers", response_model=CustomerReport, summary="Customer report")
def customer_report(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(20, ge=1, le=100),
) -> CustomerReport:
    return ReportService(db).customer_report(date_from, date_to, limit)


@router.get(
    "/business-summary",
    response_model=BusinessSummaryReport,
    summary="One page business summary",
)
def business_summary(
    db: DbSession,
    _: CurrentUser,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> BusinessSummaryReport:
    return ReportService(db).business_summary(date_from, date_to)
