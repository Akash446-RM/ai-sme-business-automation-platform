"""Customer management business logic."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.repositories.sale_repository import SaleRepository
from app.schemas.customer import (
    CustomerCreate,
    CustomerDetail,
    CustomerPurchaseSummary,
    CustomerRead,
    CustomerUpdate,
)

logger = logging.getLogger(__name__)

CODE_PREFIX = "CUST"


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CustomerRepository(db)
        self.sale_repo = SaleRepository(db)

    def get(self, customer_id: int) -> Customer:
        customer = self.repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} was not found.")
        return customer

    def list_customers(self, params: PageParams, **filters) -> Tuple[List[Customer], int]:
        return self.repo.paginate(self.repo.build_query(**filters), params)

    def cities(self) -> List[str]:
        return self.repo.cities()

    def create(self, payload: CustomerCreate) -> Customer:
        code = (payload.customer_code or self._generate_code()).strip().upper()
        if self.repo.get_by_code(code):
            raise ConflictError(f"Customer code '{code}' is already in use.")
        if payload.phone and self.repo.get_by_phone(payload.phone):
            raise ConflictError(f"Phone number '{payload.phone}' is already registered.")

        data = payload.model_dump(exclude={"customer_code"})
        if data.get("email"):
            data["email"] = str(data["email"]).lower()
        customer = self.repo.create(**data, customer_code=code, is_active=True)
        self.db.commit()
        self.db.refresh(customer)
        logger.info("Created customer %s (%s)", customer.customer_code, customer.name)
        return customer

    def update(self, customer_id: int, payload: CustomerUpdate) -> Customer:
        customer = self.get(customer_id)
        values = payload.model_dump(exclude_unset=True)
        if values.get("phone"):
            existing = self.repo.get_by_phone(values["phone"])
            if existing and existing.id != customer_id:
                raise ConflictError(
                    f"Phone number '{values['phone']}' is already registered."
                )
        if values.get("email"):
            values["email"] = str(values["email"]).lower()
        self.repo.update(customer, values)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def delete(self, customer_id: int) -> None:
        customer = self.get(customer_id)
        if self.repo.has_sales(customer_id):
            raise ConflictError(
                "This customer has purchase history and cannot be deleted. "
                "Deactivate the record instead."
            )
        self.repo.delete(customer)
        self.db.commit()

    def deactivate(self, customer_id: int) -> Customer:
        customer = self.get(customer_id)
        customer.is_active = False
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def detail(self, customer_id: int) -> CustomerDetail:
        """Customer record enriched with real purchase behaviour."""
        customer = self.get(customer_id)
        detail = CustomerDetail.model_validate(CustomerRead.model_validate(customer).model_dump())

        row = self.repo.purchase_summary(customer_id)
        if row and int(row[0] or 0) > 0:
            orders = int(row[0])
            total_spent = Decimal(str(row[1] or 0))
            first_purchase = row[2]
            last_purchase = row[3]
            days_since = (
                (datetime.now() - last_purchase).days if last_purchase else None
            )
            detail.purchase_summary = CustomerPurchaseSummary(
                customer_id=customer.id,
                customer_code=customer.customer_code,
                name=customer.name,
                total_orders=orders,
                total_spent=total_spent,
                average_order_value=(total_spent / orders).quantize(Decimal("0.01")),
                first_purchase=first_purchase,
                last_purchase=last_purchase,
                days_since_last_purchase=days_since,
                favourite_category=self.sale_repo.customer_favourite_category(customer_id),
            )
        detail.recent_bills = self.sale_repo.customer_recent_bills(customer_id)
        return detail

    def _generate_code(self) -> str:
        return f"{CODE_PREFIX}{self.repo.next_code_sequence():05d}"
