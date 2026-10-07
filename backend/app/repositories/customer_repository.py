"""Data access for customers."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.sale import Sale
from app.repositories.base import BaseRepository

SORTABLE_FIELDS = {
    "name": Customer.name,
    "customer_code": Customer.customer_code,
    "city": Customer.city,
    "created_at": Customer.created_at,
}


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Customer)

    def get_by_code(self, code: str) -> Optional[Customer]:
        return self.db.execute(
            select(Customer).where(Customer.customer_code == code.strip().upper())
        ).scalar_one_or_none()

    def get_by_phone(self, phone: str) -> Optional[Customer]:
        return self.db.execute(
            select(Customer).where(Customer.phone == phone.strip())
        ).scalar_one_or_none()

    def build_query(
        self,
        *,
        search: Optional[str] = None,
        city: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
    ) -> Select:
        statement = select(Customer)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Customer.name.ilike(pattern),
                    Customer.customer_code.ilike(pattern),
                    Customer.phone.ilike(pattern),
                    Customer.email.ilike(pattern),
                )
            )
        if city:
            statement = statement.where(Customer.city == city)
        if is_active is not None:
            statement = statement.where(Customer.is_active.is_(is_active))

        column = SORTABLE_FIELDS.get(sort_by, Customer.name)
        return statement.order_by(
            column.desc() if sort_dir.lower() == "desc" else column.asc(), Customer.id
        )

    def next_code_sequence(self) -> int:
        """Highest numeric suffix currently used by a customer code."""
        latest = self.db.execute(
            select(Customer.customer_code).order_by(Customer.id.desc()).limit(1)
        ).scalar_one_or_none()
        if not latest:
            return 1
        digits = "".join(character for character in latest if character.isdigit())
        return int(digits) + 1 if digits else 1

    def cities(self) -> List[str]:
        return [
            row[0]
            for row in self.db.execute(
                select(Customer.city)
                .where(Customer.city.is_not(None))
                .distinct()
                .order_by(Customer.city)
            ).all()
        ]

    def purchase_summary(self, customer_id: int) -> Optional[tuple]:
        """Aggregate order count, spend and purchase dates for a customer."""
        return self.db.execute(
            select(
                func.count(Sale.id),
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.min(Sale.sale_date),
                func.max(Sale.sale_date),
            ).where(Sale.customer_id == customer_id)
        ).one_or_none()

    def has_sales(self, customer_id: int) -> bool:
        return bool(
            self.db.execute(
                select(func.count(Sale.id)).where(Sale.customer_id == customer_id)
            ).scalar_one()
        )

    def count_active(self) -> int:
        return int(
            self.db.execute(
                select(func.count(Customer.id)).where(Customer.is_active.is_(True))
            ).scalar_one()
        )
