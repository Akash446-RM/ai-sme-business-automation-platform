"""Data access for sales and sale items."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.employee import Employee
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.repositories.base import BaseRepository

SORTABLE_FIELDS = {
    "sale_date": Sale.sale_date,
    "bill_no": Sale.bill_no,
    "total_amount": Sale.total_amount,
    "created_at": Sale.created_at,
}


class SaleRepository(BaseRepository[Sale]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Sale)

    def get_with_items(self, sale_id: int) -> Optional[Sale]:
        return self.db.execute(
            select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id)
        ).scalar_one_or_none()

    def get_by_bill_no(self, bill_no: str) -> Optional[Sale]:
        return self.db.execute(
            select(Sale).options(selectinload(Sale.items)).where(Sale.bill_no == bill_no)
        ).scalar_one_or_none()

    def build_query(
        self,
        *,
        search: Optional[str] = None,
        customer_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        payment_method: Optional[str] = None,
        sort_by: str = "sale_date",
        sort_dir: str = "desc",
    ) -> Select:
        statement = select(Sale)
        if search:
            statement = statement.where(Sale.bill_no.ilike(f"%{search.strip()}%"))
        if customer_id:
            statement = statement.where(Sale.customer_id == customer_id)
        if employee_id:
            statement = statement.where(Sale.employee_id == employee_id)
        if date_from:
            statement = statement.where(Sale.sale_date >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            statement = statement.where(
                Sale.sale_date < datetime.combine(date_to + timedelta(days=1), datetime.min.time())
            )
        if min_amount is not None:
            statement = statement.where(Sale.total_amount >= min_amount)
        if max_amount is not None:
            statement = statement.where(Sale.total_amount <= max_amount)
        if payment_method:
            statement = statement.where(Sale.payment_method == payment_method)

        column = SORTABLE_FIELDS.get(sort_by, Sale.sale_date)
        return statement.order_by(
            column.desc() if sort_dir.lower() == "desc" else column.asc(), Sale.id.desc()
        )

    def next_bill_sequence(self, prefix: str) -> int:
        """Next numeric suffix for bills sharing the supplied prefix."""
        latest = self.db.execute(
            select(Sale.bill_no)
            .where(Sale.bill_no.like(f"{prefix}%"))
            .order_by(Sale.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if not latest:
            return 1
        suffix = latest[len(prefix) :]
        return int(suffix) + 1 if suffix.isdigit() else 1

    def display_names(self, sale_ids: List[int]) -> dict[int, tuple]:
        """Map sale id -> (customer_name, employee_name, item_count)."""
        if not sale_ids:
            return {}
        item_counts = dict(
            self.db.execute(
                select(SaleItem.sale_id, func.count(SaleItem.id))
                .where(SaleItem.sale_id.in_(sale_ids))
                .group_by(SaleItem.sale_id)
            ).all()
        )
        rows = self.db.execute(
            select(Sale.id, Customer.name, Employee.name)
            .select_from(Sale)
            .outerjoin(Customer, Sale.customer_id == Customer.id)
            .outerjoin(Employee, Sale.employee_id == Employee.id)
            .where(Sale.id.in_(sale_ids))
        ).all()
        return {
            row[0]: (row[1], row[2], item_counts.get(row[0], 0)) for row in rows
        }

    def recent(self, limit: int = 10) -> List[Sale]:
        return list(
            self.db.execute(
                select(Sale).order_by(Sale.sale_date.desc(), Sale.id.desc()).limit(limit)
            ).scalars()
        )

    def customer_recent_bills(self, customer_id: int, limit: int = 5) -> List[str]:
        return [
            row[0]
            for row in self.db.execute(
                select(Sale.bill_no)
                .where(Sale.customer_id == customer_id)
                .order_by(Sale.sale_date.desc())
                .limit(limit)
            ).all()
        ]

    def customer_favourite_category(self, customer_id: int) -> Optional[str]:
        from app.models.product import Product

        row = self.db.execute(
            select(Product.category, func.sum(SaleItem.line_total).label("revenue"))
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .where(Sale.customer_id == customer_id)
            .group_by(Product.category)
            .order_by(func.sum(SaleItem.line_total).desc())
            .limit(1)
        ).first()
        return row[0] if row else None

    def product_has_sales(self, product_id: int) -> bool:
        return bool(
            self.db.execute(
                select(func.count(SaleItem.id)).where(SaleItem.product_id == product_id)
            ).scalar_one()
        )

    def count_sales(self) -> int:
        return int(self.db.execute(select(func.count(Sale.id))).scalar_one())

    def total_revenue(self) -> float:
        value = self.db.execute(
            select(func.coalesce(func.sum(Sale.total_amount), 0))
        ).scalar_one()
        return float(value or 0)

    def latest_sale_date(self) -> Optional[datetime]:
        return self.db.execute(select(func.max(Sale.sale_date))).scalar_one_or_none()

    def earliest_sale_date(self) -> Optional[datetime]:
        return self.db.execute(select(func.min(Sale.sale_date))).scalar_one_or_none()
