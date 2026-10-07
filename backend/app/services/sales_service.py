"""Sales workflow.

Creating a sale is the most safety critical operation in the platform. It
validates products and stock, computes the bill, writes the sale and its line
items, decrements inventory and appends to the inventory ledger - all inside a
single database transaction. Any failure rolls the whole thing back so stock
can never drift away from the recorded sales history.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from app.core.pagination import PageParams
from app.models.enums import TransactionType
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.repositories.customer_repository import CustomerRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.sale_repository import SaleRepository
from app.schemas.sale import (
    SaleCreate,
    SaleCreatedResponse,
    SaleDetail,
    SaleListItem,
    SaleRead,
    StockUpdateInfo,
)

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")
BILL_PREFIX = "INV"


def money(value: Decimal | float | int) -> Decimal:
    """Round a monetary value to two decimal places, half up."""
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


class SalesService:
    """Owns the end to end sale creation workflow."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SaleRepository(db)
        self.product_repo = ProductRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.inventory_repo = InventoryRepository(db)

    # -- reads ------------------------------------------------------------
    def get(self, sale_id: int) -> Sale:
        sale = self.repo.get_with_items(sale_id)
        if sale is None:
            raise NotFoundError(f"Sale {sale_id} was not found.")
        return sale

    def get_detail(self, sale_id: int) -> SaleDetail:
        sale = self.get(sale_id)
        return self._to_detail(sale)

    def get_by_bill_no(self, bill_no: str) -> SaleDetail:
        sale = self.repo.get_by_bill_no(bill_no.strip().upper())
        if sale is None:
            raise NotFoundError(f"Bill '{bill_no}' was not found.")
        return self._to_detail(sale)

    def list_sales(self, params: PageParams, **filters) -> Tuple[List[SaleListItem], int]:
        statement = self.repo.build_query(**filters)
        sales, total = self.repo.paginate(statement, params)
        names = self.repo.display_names([sale.id for sale in sales])
        items: List[SaleListItem] = []
        for sale in sales:
            customer_name, employee_name, item_count = names.get(sale.id, (None, None, 0))
            row = SaleListItem.model_validate(SaleRead.model_validate(sale).model_dump())
            row.customer_name = customer_name
            row.employee_name = employee_name
            row.item_count = item_count
            items.append(row)
        return items, total

    def recent(self, limit: int = 10) -> List[SaleListItem]:
        sales = self.repo.recent(limit)
        names = self.repo.display_names([sale.id for sale in sales])
        result: List[SaleListItem] = []
        for sale in sales:
            customer_name, employee_name, item_count = names.get(sale.id, (None, None, 0))
            row = SaleListItem.model_validate(SaleRead.model_validate(sale).model_dump())
            row.customer_name = customer_name
            row.employee_name = employee_name
            row.item_count = item_count
            result.append(row)
        return result

    # -- the sales workflow ----------------------------------------------
    def create_sale(
        self, payload: SaleCreate, *, user_id: Optional[int] = None
    ) -> SaleCreatedResponse:
        """Execute the full sale workflow atomically."""
        self._validate_references(payload)

        products = self._load_and_lock_products(payload)
        self._validate_stock(payload, products)

        gst_rate = (
            payload.gst_rate
            if payload.gst_rate is not None
            else Decimal(str(settings.gst_rate))
        )
        line_data, subtotal = self._build_lines(payload, products)

        if payload.discount_amount > subtotal:
            raise ValidationError(
                "Bill level discount cannot exceed the subtotal.",
                {"subtotal": str(subtotal), "discount": str(payload.discount_amount)},
            )

        taxable_amount = money(subtotal - payload.discount_amount)
        gst_amount = money(taxable_amount * gst_rate / Decimal("100"))
        total_amount = money(taxable_amount + gst_amount)

        sale_date = payload.sale_date or datetime.now()

        try:
            sale = Sale(
                bill_no=self._generate_bill_no(sale_date),
                customer_id=payload.customer_id,
                employee_id=payload.employee_id,
                subtotal=money(subtotal),
                discount_amount=money(payload.discount_amount),
                taxable_amount=taxable_amount,
                gst_rate=gst_rate,
                gst_amount=gst_amount,
                total_amount=total_amount,
                payment_method=payload.payment_method,
                notes=payload.notes,
                sale_date=sale_date,
            )
            self.db.add(sale)
            self.db.flush()  # assign sale.id

            stock_updates: List[StockUpdateInfo] = []
            alerts: List[str] = []

            for line in line_data:
                product: Product = line["product"]
                quantity: int = line["quantity"]

                self.db.add(
                    SaleItem(
                        sale_id=sale.id,
                        product_id=product.id,
                        product_name=product.name,
                        quantity=quantity,
                        unit_price=line["unit_price"],
                        unit_cost=product.cost_price,
                        discount_amount=line["discount_amount"],
                        line_total=line["line_total"],
                    )
                )

                previous_stock = product.stock
                new_stock = previous_stock - quantity
                product.stock = new_stock

                self.inventory_repo.create(
                    product_id=product.id,
                    transaction_type=TransactionType.SALE,
                    quantity=-quantity,
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    reference=sale.bill_no,
                    notes=f"Sold {quantity} unit(s) on bill {sale.bill_no}",
                    created_by=user_id,
                )

                below_reorder = new_stock <= product.reorder_level
                stock_updates.append(
                    StockUpdateInfo(
                        product_id=product.id,
                        product_name=product.name,
                        previous_stock=previous_stock,
                        new_stock=new_stock,
                        below_reorder_level=below_reorder,
                    )
                )
                if new_stock <= 0:
                    alerts.append(f"{product.name} is now out of stock.")
                elif below_reorder:
                    alerts.append(
                        f"{product.name} has fallen to {new_stock} units, "
                        f"at or below its reorder level of {product.reorder_level}."
                    )

            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            logger.warning("Sale creation failed due to a constraint: %s", exc)
            raise ConflictError(
                "The sale could not be saved because of a data conflict. Please retry."
            ) from exc
        except Exception:
            self.db.rollback()
            logger.exception("Sale creation failed; transaction rolled back")
            raise

        self.db.refresh(sale)
        logger.info(
            "Sale %s created: %s line(s), total %s", sale.bill_no, len(line_data), total_amount
        )
        return SaleCreatedResponse(
            sale=self._to_detail(self.get(sale.id)),
            stock_updates=stock_updates,
            alerts_raised=alerts,
        )

    def void_sale(self, sale_id: int, *, user_id: Optional[int] = None) -> None:
        """Reverse a sale, returning stock and writing compensating ledger rows."""
        sale = self.get(sale_id)
        try:
            for item in sale.items:
                product = self.product_repo.get(item.product_id)
                if product is None:
                    continue
                previous_stock = product.stock
                new_stock = previous_stock + item.quantity
                product.stock = new_stock
                self.inventory_repo.create(
                    product_id=product.id,
                    transaction_type=TransactionType.RETURN,
                    quantity=item.quantity,
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    reference=f"VOID-{sale.bill_no}",
                    notes=f"Reversal of bill {sale.bill_no}",
                    created_by=user_id,
                )
            self.db.delete(sale)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Void failed for sale %s", sale_id)
            raise
        logger.info("Sale %s voided and stock restored", sale.bill_no)

    # -- internals --------------------------------------------------------
    def _validate_references(self, payload: SaleCreate) -> None:
        if payload.customer_id and not self.customer_repo.get(payload.customer_id):
            raise NotFoundError(f"Customer {payload.customer_id} was not found.")
        if payload.employee_id and not self.employee_repo.get(payload.employee_id):
            raise NotFoundError(f"Employee {payload.employee_id} was not found.")

    def _load_and_lock_products(self, payload: SaleCreate) -> Dict[int, Product]:
        requested_ids = [item.product_id for item in payload.items]
        products = {
            product.id: product
            for product in self.product_repo.lock_for_update(requested_ids)
        }
        missing = sorted(set(requested_ids) - set(products))
        if missing:
            raise NotFoundError(
                "One or more products in this sale do not exist.",
                {"missing_product_ids": missing},
            )
        inactive = [
            products[pid].name for pid in requested_ids if not products[pid].is_active
        ]
        if inactive:
            raise ValidationError(
                "One or more products are inactive and cannot be sold.",
                {"inactive_products": inactive},
            )
        return products

    def _validate_stock(self, payload: SaleCreate, products: Dict[int, Product]) -> None:
        shortages = [
            {
                "product_id": item.product_id,
                "product_name": products[item.product_id].name,
                "requested": item.quantity,
                "available": products[item.product_id].stock,
            }
            for item in payload.items
            if products[item.product_id].stock < item.quantity
        ]
        if shortages:
            names = ", ".join(entry["product_name"] for entry in shortages)
            raise InsufficientStockError(
                f"Not enough stock for: {names}.", {"shortages": shortages}
            )

    def _build_lines(
        self, payload: SaleCreate, products: Dict[int, Product]
    ) -> Tuple[List[dict], Decimal]:
        lines: List[dict] = []
        subtotal = Decimal("0.00")
        for item in payload.items:
            product = products[item.product_id]
            unit_price = money(
                item.unit_price if item.unit_price is not None else product.selling_price
            )
            gross = money(unit_price * item.quantity)
            discount = money(item.discount_amount)
            if discount > gross:
                raise ValidationError(
                    f"Line discount for '{product.name}' exceeds the line value.",
                    {"line_value": str(gross), "discount": str(discount)},
                )
            line_total = money(gross - discount)
            subtotal += line_total
            lines.append(
                {
                    "product": product,
                    "quantity": item.quantity,
                    "unit_price": unit_price,
                    "discount_amount": discount,
                    "line_total": line_total,
                }
            )
        return lines, money(subtotal)

    def _generate_bill_no(self, sale_date: datetime) -> str:
        prefix = f"{BILL_PREFIX}{sale_date:%Y%m}-"
        sequence = self.repo.next_bill_sequence(prefix)
        return f"{prefix}{sequence:05d}"

    def _to_detail(self, sale: Sale) -> SaleDetail:
        detail = SaleDetail.model_validate(sale)
        names = self.repo.display_names([sale.id]).get(sale.id)
        if names:
            detail.customer_name, detail.employee_name, _ = names
        return detail
