"""Aggregation queries powering analytics, dashboards and reports.

Everything here is expressed as SQL aggregation so the database does the work.
No endpoint ever loads a full table into Python to compute a total.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.employee import Employee
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem


def day_bounds(target: date) -> Tuple[datetime, datetime]:
    start = datetime.combine(target, datetime.min.time())
    return start, start + timedelta(days=1)


def range_bounds(date_from: date, date_to: date) -> Tuple[datetime, datetime]:
    return (
        datetime.combine(date_from, datetime.min.time()),
        datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
    )


class AnalyticsRepository:
    """Read only aggregation helpers over the sales tables."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- period totals ----------------------------------------------------
    def period_totals(self, date_from: date, date_to: date) -> Tuple[float, int, int]:
        """Revenue, transaction count and units sold within an inclusive range."""
        start, end = range_bounds(date_from, date_to)
        revenue, transactions = self.db.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.count(Sale.id),
            ).where(Sale.sale_date >= start, Sale.sale_date < end)
        ).one()
        units = self.db.execute(
            select(func.coalesce(func.sum(SaleItem.quantity), 0))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(Sale.sale_date >= start, Sale.sale_date < end)
        ).scalar_one()
        return float(revenue or 0), int(transactions or 0), int(units or 0)

    def gross_profit(self, date_from: date, date_to: date) -> float:
        """Revenue minus cost of goods sold, using the price snapshot on each line."""
        start, end = range_bounds(date_from, date_to)
        value = self.db.execute(
            select(
                func.coalesce(
                    func.sum(SaleItem.line_total - SaleItem.unit_cost * SaleItem.quantity), 0
                )
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(Sale.sale_date >= start, Sale.sale_date < end)
        ).scalar_one()
        return float(value or 0)

    # -- trends -----------------------------------------------------------
    def revenue_trend(
        self, date_from: date, date_to: date, granularity: str = "day"
    ) -> List[tuple]:
        """Revenue grouped by day, week or month.

        The period expression is dialect aware so the same code works on MySQL
        in production and SQLite in tests.
        """
        start, end = range_bounds(date_from, date_to)
        dialect = self.db.bind.dialect.name if self.db.bind else "mysql"

        if granularity == "month":
            if dialect == "sqlite":
                period = func.strftime("%Y-%m", Sale.sale_date)
            else:
                period = func.date_format(Sale.sale_date, "%Y-%m")
        elif granularity == "week":
            if dialect == "sqlite":
                period = func.strftime("%Y-W%W", Sale.sale_date)
            else:
                period = func.concat(
                    func.year(Sale.sale_date), "-W", func.lpad(func.week(Sale.sale_date, 3), 2, "0")
                )
        else:
            # Group by calendar day as a plain string so both dialects agree.
            period = (
                func.strftime("%Y-%m-%d", Sale.sale_date)
                if dialect == "sqlite"
                else func.date_format(Sale.sale_date, "%Y-%m-%d")
            )

        units_subquery = (
            select(
                SaleItem.sale_id.label("sale_id"),
                func.sum(SaleItem.quantity).label("units"),
            )
            .group_by(SaleItem.sale_id)
            .subquery()
        )

        rows = self.db.execute(
            select(
                period.label("period"),
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.count(Sale.id),
                func.coalesce(func.sum(units_subquery.c.units), 0),
            )
            .select_from(Sale)
            .outerjoin(units_subquery, units_subquery.c.sale_id == Sale.id)
            .where(Sale.sale_date >= start, Sale.sale_date < end)
            .group_by(period)
            .order_by(period)
        ).all()
        return list(rows)

    # -- product and category --------------------------------------------
    def product_performance(
        self,
        date_from: date,
        date_to: date,
        *,
        limit: int = 10,
        ascending: bool = False,
        category: Optional[str] = None,
    ) -> List[tuple]:
        start, end = range_bounds(date_from, date_to)
        revenue_expr = func.coalesce(func.sum(SaleItem.line_total), 0)
        order = revenue_expr.asc() if ascending else revenue_expr.desc()

        statement = (
            select(
                Product.id,
                Product.name,
                Product.sku,
                Product.category,
                func.coalesce(func.sum(SaleItem.quantity), 0),
                revenue_expr,
                func.coalesce(
                    func.sum(SaleItem.line_total - SaleItem.unit_cost * SaleItem.quantity), 0
                ),
                func.count(func.distinct(SaleItem.sale_id)),
                Product.stock,
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .where(Sale.sale_date >= start, Sale.sale_date < end)
        )
        if category:
            statement = statement.where(Product.category == category)

        return list(
            self.db.execute(
                statement.group_by(
                    Product.id, Product.name, Product.sku, Product.category, Product.stock
                )
                .order_by(order)
                .limit(limit)
            ).all()
        )

    def product_revenue_map(self, date_from: date, date_to: date) -> dict[int, float]:
        """product_id -> revenue, used for growth comparisons."""
        start, end = range_bounds(date_from, date_to)
        rows = self.db.execute(
            select(SaleItem.product_id, func.coalesce(func.sum(SaleItem.line_total), 0))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(Sale.sale_date >= start, Sale.sale_date < end)
            .group_by(SaleItem.product_id)
        ).all()
        return {int(row[0]): float(row[1] or 0) for row in rows}

    def product_units_map(self, date_from: date, date_to: date) -> dict[int, int]:
        start, end = range_bounds(date_from, date_to)
        rows = self.db.execute(
            select(SaleItem.product_id, func.coalesce(func.sum(SaleItem.quantity), 0))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(Sale.sale_date >= start, Sale.sale_date < end)
            .group_by(SaleItem.product_id)
        ).all()
        return {int(row[0]): int(row[1] or 0) for row in rows}

    def category_performance(self, date_from: date, date_to: date) -> List[tuple]:
        start, end = range_bounds(date_from, date_to)
        return list(
            self.db.execute(
                select(
                    Product.category,
                    func.coalesce(func.sum(SaleItem.quantity), 0),
                    func.coalesce(func.sum(SaleItem.line_total), 0),
                    func.coalesce(
                        func.sum(SaleItem.line_total - SaleItem.unit_cost * SaleItem.quantity), 0
                    ),
                    func.count(func.distinct(SaleItem.sale_id)),
                    func.count(func.distinct(Product.id)),
                )
                .select_from(SaleItem)
                .join(Sale, SaleItem.sale_id == Sale.id)
                .join(Product, SaleItem.product_id == Product.id)
                .where(Sale.sale_date >= start, Sale.sale_date < end)
                .group_by(Product.category)
                .order_by(func.sum(SaleItem.line_total).desc())
            ).all()
        )

    def category_revenue_map(self, date_from: date, date_to: date) -> dict[str, float]:
        start, end = range_bounds(date_from, date_to)
        rows = self.db.execute(
            select(Product.category, func.coalesce(func.sum(SaleItem.line_total), 0))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .where(Sale.sale_date >= start, Sale.sale_date < end)
            .group_by(Product.category)
        ).all()
        return {str(row[0]): float(row[1] or 0) for row in rows}

    # -- customers and employees -----------------------------------------
    def top_customers(self, date_from: date, date_to: date, limit: int = 10) -> List[tuple]:
        start, end = range_bounds(date_from, date_to)
        return list(
            self.db.execute(
                select(
                    Customer.id,
                    Customer.customer_code,
                    Customer.name,
                    Customer.city,
                    func.count(Sale.id),
                    func.coalesce(func.sum(Sale.total_amount), 0),
                    func.max(Sale.sale_date),
                )
                .select_from(Sale)
                .join(Customer, Sale.customer_id == Customer.id)
                .where(Sale.sale_date >= start, Sale.sale_date < end)
                .group_by(Customer.id, Customer.customer_code, Customer.name, Customer.city)
                .order_by(func.sum(Sale.total_amount).desc())
                .limit(limit)
            ).all()
        )

    def employee_leaderboard(
        self, date_from: date, date_to: date, limit: int = 10
    ) -> List[tuple]:
        start, end = range_bounds(date_from, date_to)
        return list(
            self.db.execute(
                select(
                    Employee.id,
                    Employee.name,
                    Employee.role,
                    func.count(Sale.id),
                    func.coalesce(func.sum(Sale.total_amount), 0),
                )
                .select_from(Sale)
                .join(Employee, Sale.employee_id == Employee.id)
                .where(Sale.sale_date >= start, Sale.sale_date < end)
                .group_by(Employee.id, Employee.name, Employee.role)
                .order_by(func.sum(Sale.total_amount).desc())
                .limit(limit)
            ).all()
        )

    def active_customer_count(self, date_from: date, date_to: date) -> int:
        start, end = range_bounds(date_from, date_to)
        return int(
            self.db.execute(
                select(func.count(func.distinct(Sale.customer_id))).where(
                    Sale.sale_date >= start, Sale.sale_date < end
                )
            ).scalar_one()
        )

    # -- behavioural patterns ---------------------------------------------
    def payment_mix(self, date_from: date, date_to: date) -> List[tuple]:
        start, end = range_bounds(date_from, date_to)
        return list(
            self.db.execute(
                select(
                    Sale.payment_method,
                    func.count(Sale.id),
                    func.coalesce(func.sum(Sale.total_amount), 0),
                )
                .where(Sale.sale_date >= start, Sale.sale_date < end)
                .group_by(Sale.payment_method)
                .order_by(func.sum(Sale.total_amount).desc())
            ).all()
        )

    def hourly_pattern(self, date_from: date, date_to: date) -> List[tuple]:
        start, end = range_bounds(date_from, date_to)
        dialect = self.db.bind.dialect.name if self.db.bind else "mysql"
        hour = (
            func.cast(func.strftime("%H", Sale.sale_date), func.INTEGER().type)
            if dialect == "sqlite"
            else func.hour(Sale.sale_date)
        )
        return list(
            self.db.execute(
                select(
                    hour.label("hour"),
                    func.count(Sale.id),
                    func.coalesce(func.sum(Sale.total_amount), 0),
                )
                .where(Sale.sale_date >= start, Sale.sale_date < end)
                .group_by(hour)
                .order_by(hour)
            ).all()
        )

    def weekday_pattern(self, date_from: date, date_to: date) -> List[tuple]:
        start, end = range_bounds(date_from, date_to)
        dialect = self.db.bind.dialect.name if self.db.bind else "mysql"
        # Normalise to 0 = Monday for both dialects.
        weekday = (
            func.strftime("%w", Sale.sale_date)
            if dialect == "sqlite"
            else func.weekday(Sale.sale_date)
        )
        rows = self.db.execute(
            select(
                weekday.label("weekday"),
                func.count(Sale.id),
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.count(func.distinct(func.substr(Sale.sale_date, 1, 10))),
            )
            .where(Sale.sale_date >= start, Sale.sale_date < end)
            .group_by(weekday)
            .order_by(weekday)
        ).all()

        normalised: List[tuple] = []
        for row in rows:
            index = int(row[0])
            if dialect == "sqlite":
                index = (index - 1) % 7  # sqlite: 0 = Sunday
            normalised.append((index, int(row[1]), float(row[2] or 0), int(row[3] or 1)))
        normalised.sort(key=lambda item: item[0])
        return normalised

    # -- dataset boundaries -----------------------------------------------
    def data_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        row = self.db.execute(
            select(func.min(Sale.sale_date), func.max(Sale.sale_date))
        ).one()
        return row[0], row[1]
