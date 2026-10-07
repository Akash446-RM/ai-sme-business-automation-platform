"""Employee management business logic."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.models.employee import Employee
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.employee import EmployeeCreate, EmployeePerformance, EmployeeUpdate

logger = logging.getLogger(__name__)

CODE_PREFIX = "EMP"


class EmployeeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EmployeeRepository(db)

    def get(self, employee_id: int) -> Employee:
        employee = self.repo.get(employee_id)
        if employee is None:
            raise NotFoundError(f"Employee {employee_id} was not found.")
        return employee

    def list_employees(self, params: PageParams, **filters) -> Tuple[List[Employee], int]:
        return self.repo.paginate(self.repo.build_query(**filters), params)

    def roles(self) -> List[str]:
        return self.repo.roles()

    def create(self, payload: EmployeeCreate) -> Employee:
        code = (payload.employee_code or self._generate_code()).strip().upper()
        if self.repo.get_by_code(code):
            raise ConflictError(f"Employee code '{code}' is already in use.")

        data = payload.model_dump(exclude={"employee_code"})
        if data.get("email"):
            data["email"] = str(data["email"]).lower()
        employee = self.repo.create(**data, employee_code=code, is_active=True)
        self.db.commit()
        self.db.refresh(employee)
        logger.info("Created employee %s (%s)", employee.employee_code, employee.name)
        return employee

    def update(self, employee_id: int, payload: EmployeeUpdate) -> Employee:
        employee = self.get(employee_id)
        values = payload.model_dump(exclude_unset=True)
        if values.get("email"):
            values["email"] = str(values["email"]).lower()
        self.repo.update(employee, values)
        self.db.commit()
        self.db.refresh(employee)
        return employee

    def delete(self, employee_id: int) -> None:
        employee = self.get(employee_id)
        if self.repo.has_sales(employee_id):
            raise ConflictError(
                "This employee is linked to recorded sales and cannot be deleted. "
                "Deactivate the record instead."
            )
        self.repo.delete(employee)
        self.db.commit()

    def deactivate(self, employee_id: int) -> Employee:
        employee = self.get(employee_id)
        employee.is_active = False
        self.db.commit()
        self.db.refresh(employee)
        return employee

    def performance(self, employee_id: int) -> EmployeePerformance:
        employee = self.get(employee_id)
        row = self.repo.performance(employee_id)
        total_sales = int(row[0] or 0) if row else 0
        total_revenue = Decimal(str(row[1] or 0)) if row else Decimal("0")
        average = (
            (total_revenue / total_sales).quantize(Decimal("0.01"))
            if total_sales
            else Decimal("0.00")
        )
        return EmployeePerformance(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            name=employee.name,
            role=employee.role,
            total_sales=total_sales,
            total_revenue=total_revenue,
            average_order_value=average,
            last_sale_at=row[2] if row else None,
        )

    def _generate_code(self) -> str:
        return f"{CODE_PREFIX}{self.repo.next_code_sequence():04d}"
