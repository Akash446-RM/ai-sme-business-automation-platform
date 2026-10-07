"""Data access for employees."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.sale import Sale
from app.repositories.base import BaseRepository

SORTABLE_FIELDS = {
    "name": Employee.name,
    "employee_code": Employee.employee_code,
    "role": Employee.role,
    "hired_on": Employee.hired_on,
    "created_at": Employee.created_at,
}


class EmployeeRepository(BaseRepository[Employee]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Employee)

    def get_by_code(self, code: str) -> Optional[Employee]:
        return self.db.execute(
            select(Employee).where(Employee.employee_code == code.strip().upper())
        ).scalar_one_or_none()

    def build_query(
        self,
        *,
        search: Optional[str] = None,
        role: Optional[str] = None,
        department: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
    ) -> Select:
        statement = select(Employee)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Employee.name.ilike(pattern),
                    Employee.employee_code.ilike(pattern),
                    Employee.email.ilike(pattern),
                    Employee.phone.ilike(pattern),
                )
            )
        if role:
            statement = statement.where(Employee.role == role)
        if department:
            statement = statement.where(Employee.department == department)
        if is_active is not None:
            statement = statement.where(Employee.is_active.is_(is_active))

        column = SORTABLE_FIELDS.get(sort_by, Employee.name)
        return statement.order_by(
            column.desc() if sort_dir.lower() == "desc" else column.asc(), Employee.id
        )

    def next_code_sequence(self) -> int:
        latest = self.db.execute(
            select(Employee.employee_code).order_by(Employee.id.desc()).limit(1)
        ).scalar_one_or_none()
        if not latest:
            return 1
        digits = "".join(character for character in latest if character.isdigit())
        return int(digits) + 1 if digits else 1

    def roles(self) -> List[str]:
        return [
            row[0]
            for row in self.db.execute(
                select(Employee.role).distinct().order_by(Employee.role)
            ).all()
        ]

    def performance(self, employee_id: int) -> Optional[tuple]:
        return self.db.execute(
            select(
                func.count(Sale.id),
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.max(Sale.sale_date),
            ).where(Sale.employee_id == employee_id)
        ).one_or_none()

    def has_sales(self, employee_id: int) -> bool:
        return bool(
            self.db.execute(
                select(func.count(Sale.id)).where(Sale.employee_id == employee_id)
            ).scalar_one()
        )

    def count_active(self) -> int:
        return int(
            self.db.execute(
                select(func.count(Employee.id)).where(Employee.is_active.is_(True))
            ).scalar_one()
        )
