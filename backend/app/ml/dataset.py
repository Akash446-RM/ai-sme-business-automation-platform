"""Dataset extraction for the machine learning pipeline.

Two datasets are produced directly from the transactional tables:

* ``daily_sales``          - one row per calendar day (business level revenue)
* ``daily_product_demand`` - one row per product per day (item level demand)

Both are gap filled with explicit zeros. Days with no sales are real
information: a model that never sees a zero cannot learn that demand stops.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem

logger = logging.getLogger(__name__)

MIN_DAYS_FOR_TRAINING = 60
MIN_PRODUCT_ACTIVE_DAYS = 20


def _day_expression(db: Session):
    """Calendar day as a YYYY-MM-DD string, valid on MySQL and SQLite."""
    dialect = db.bind.dialect.name if db.bind else "mysql"
    if dialect == "sqlite":
        return func.strftime("%Y-%m-%d", Sale.sale_date)
    return func.date_format(Sale.sale_date, "%Y-%m-%d")


def sales_date_range(db: Session) -> Tuple[Optional[date], Optional[date]]:
    row = db.execute(select(func.min(Sale.sale_date), func.max(Sale.sale_date))).one()
    first, last = row
    return (first.date() if first else None, last.date() if last else None)


def load_daily_sales(db: Session) -> pd.DataFrame:
    """Business level daily revenue, transactions and units."""
    day = _day_expression(db)

    revenue_rows = db.execute(
        select(
            day.label("day"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("revenue"),
            func.count(Sale.id).label("transactions"),
            func.coalesce(func.sum(Sale.discount_amount), 0).label("discount"),
        )
        .group_by(day)
        .order_by(day)
    ).all()

    if not revenue_rows:
        return pd.DataFrame(
            columns=["date", "revenue", "transactions", "units", "discount"]
        )

    units_rows = db.execute(
        select(day.label("day"), func.coalesce(func.sum(SaleItem.quantity), 0))
        .select_from(SaleItem)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .group_by(day)
    ).all()
    units_map = {str(row[0]): int(row[1] or 0) for row in units_rows}

    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp(str(row[0])),
                "revenue": float(row[1] or 0),
                "transactions": int(row[2] or 0),
                "units": units_map.get(str(row[0]), 0),
                "discount": float(row[3] or 0),
            }
            for row in revenue_rows
        ]
    )

    # Fill missing calendar days with explicit zeros.
    full_index = pd.date_range(frame["date"].min(), frame["date"].max(), freq="D")
    frame = (
        frame.set_index("date")
        .reindex(full_index, fill_value=0)
        .rename_axis("date")
        .reset_index()
    )
    logger.info("Loaded %s days of aggregate sales history", len(frame))
    return frame


def load_daily_product_demand(
    db: Session, *, min_active_days: int = MIN_PRODUCT_ACTIVE_DAYS
) -> pd.DataFrame:
    """Product level daily demand for products with enough trading history.

    Products that have barely traded are excluded: fitting a time series model
    to three observations produces confident nonsense.
    """
    day = _day_expression(db)

    rows = db.execute(
        select(
            day.label("day"),
            SaleItem.product_id,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("units"),
            func.coalesce(func.sum(SaleItem.line_total), 0).label("revenue"),
            func.avg(SaleItem.unit_price).label("avg_price"),
        )
        .select_from(SaleItem)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .group_by(day, SaleItem.product_id)
        .order_by(day)
    ).all()

    if not rows:
        return pd.DataFrame(
            columns=["date", "product_id", "units", "revenue", "avg_price", "category"]
        )

    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp(str(row[0])),
                "product_id": int(row[1]),
                "units": int(row[2] or 0),
                "revenue": float(row[3] or 0),
                "avg_price": float(row[4] or 0),
            }
            for row in rows
        ]
    )

    active_days = frame.groupby("product_id")["date"].nunique()
    eligible = active_days[active_days >= min_active_days].index
    frame = frame[frame["product_id"].isin(eligible)].copy()
    if frame.empty:
        logger.warning("No product has at least %s active days", min_active_days)
        return frame

    # Expand each product onto the full shared calendar with zero demand days.
    calendar = pd.date_range(frame["date"].min(), frame["date"].max(), freq="D")
    products = frame["product_id"].unique()
    grid = pd.MultiIndex.from_product([products, calendar], names=["product_id", "date"])

    frame = (
        frame.set_index(["product_id", "date"])
        .reindex(grid)
        .reset_index()
    )
    frame["units"] = frame["units"].fillna(0).astype(int)
    frame["revenue"] = frame["revenue"].fillna(0.0)
    # A missing price simply means no sale that day: carry the last known price.
    frame["avg_price"] = (
        frame.groupby("product_id")["avg_price"].ffill().bfill().fillna(0.0)
    )

    catalogue = pd.DataFrame(
        db.execute(
            select(Product.id, Product.category, Product.selling_price, Product.cost_price)
        ).all(),
        columns=["product_id", "category", "selling_price", "cost_price"],
    )
    catalogue["selling_price"] = catalogue["selling_price"].astype(float)
    catalogue["cost_price"] = catalogue["cost_price"].astype(float)

    frame = frame.merge(catalogue, on="product_id", how="left")
    frame["category"] = frame["category"].fillna("Unknown")

    logger.info(
        "Loaded product demand: %s rows, %s products, %s days",
        len(frame),
        frame["product_id"].nunique(),
        frame["date"].nunique(),
    )
    return frame


def validate_dataset(frame: pd.DataFrame, *, name: str, min_rows: int) -> None:
    """Fail fast with a clear message when the data cannot support training."""
    if frame.empty:
        raise ValueError(f"{name}: dataset is empty. Seed or import sales data first.")
    if len(frame) < min_rows:
        raise ValueError(
            f"{name}: only {len(frame)} rows available, at least {min_rows} are required."
        )
    if frame.isna().any().any():
        missing = frame.columns[frame.isna().any()].tolist()
        raise ValueError(f"{name}: unexpected missing values in columns {missing}.")
