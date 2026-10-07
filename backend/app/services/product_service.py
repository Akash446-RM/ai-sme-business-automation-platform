"""Product catalogue business logic."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PageParams
from app.models.enums import TransactionType
from app.models.product import Product
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.sale_repository import SaleRepository
from app.schemas.product import CategoryInfo, ProductCreate, ProductUpdate, StockAdjustment

logger = logging.getLogger(__name__)


class ProductService:
    """Owns catalogue rules: uniqueness, pricing, stock adjustments."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProductRepository(db)
        self.inventory_repo = InventoryRepository(db)
        self.sale_repo = SaleRepository(db)

    # -- reads ------------------------------------------------------------
    def get(self, product_id: int) -> Product:
        product = self.repo.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")
        return product

    def list_products(
        self, params: PageParams, **filters
    ) -> Tuple[List[Product], int]:
        statement = self.repo.build_query(**filters)
        return self.repo.paginate(statement, params)

    def categories(self) -> List[str]:
        return self.repo.categories()

    def suppliers(self) -> List[str]:
        return self.repo.suppliers()

    def category_breakdown(self) -> List[CategoryInfo]:
        return [
            CategoryInfo(
                category=row[0],
                product_count=int(row[1]),
                total_stock=int(row[2] or 0),
                stock_value=row[3] or 0,
            )
            for row in self.repo.category_breakdown()
        ]

    def search(self, term: str, limit: int = 10) -> List[Product]:
        return self.repo.search_by_name(term, limit)

    # -- writes -----------------------------------------------------------
    def create(self, payload: ProductCreate, *, user_id: Optional[int] = None) -> Product:
        if self.repo.get_by_sku(payload.sku):
            raise ConflictError(f"A product with SKU '{payload.sku}' already exists.")
        if payload.barcode and self.repo.get_by_barcode(payload.barcode):
            raise ConflictError(f"A product with barcode '{payload.barcode}' already exists.")

        data = payload.model_dump()
        opening_stock = data.pop("stock", 0)
        product = self.repo.create(**data, stock=opening_stock, is_active=True)

        if opening_stock:
            self._record_movement(
                product=product,
                quantity=opening_stock,
                previous_stock=0,
                new_stock=opening_stock,
                transaction_type=TransactionType.INITIAL,
                reference=f"PRODUCT-{product.sku}",
                notes="Opening stock recorded at product creation",
                user_id=user_id,
            )

        self.db.commit()
        self.db.refresh(product)
        logger.info("Created product %s (%s)", product.sku, product.name)
        return product

    def update(self, product_id: int, payload: ProductUpdate) -> Product:
        product = self.get(product_id)
        values = payload.model_dump(exclude_unset=True)

        if "barcode" in values and values["barcode"]:
            existing = self.repo.get_by_barcode(values["barcode"])
            if existing and existing.id != product_id:
                raise ConflictError(
                    f"A product with barcode '{values['barcode']}' already exists."
                )

        new_cost = values.get("cost_price", product.cost_price)
        new_price = values.get("selling_price", product.selling_price)
        if new_price < new_cost:
            raise ValidationError("selling_price cannot be lower than cost_price.")

        self.repo.update(product, values)
        self.db.commit()
        self.db.refresh(product)
        return product

    def adjust_stock(
        self, product_id: int, payload: StockAdjustment, *, user_id: Optional[int] = None
    ) -> Product:
        """Apply a manual stock correction and record it in the ledger."""
        product = self.get(product_id)
        previous_stock = product.stock
        new_stock = previous_stock + payload.quantity
        if new_stock < 0:
            raise ValidationError(
                f"Adjustment would make stock negative "
                f"(current {previous_stock}, change {payload.quantity})."
            )

        product.stock = new_stock
        transaction_type = (
            TransactionType.PURCHASE if payload.quantity > 0 else TransactionType.ADJUSTMENT
        )
        self._record_movement(
            product=product,
            quantity=payload.quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            transaction_type=transaction_type,
            reference=f"ADJ-{product.sku}",
            notes=payload.reason,
            user_id=user_id,
        )
        self.db.commit()
        self.db.refresh(product)
        logger.info(
            "Stock adjusted for %s: %s -> %s (%s)",
            product.sku,
            previous_stock,
            new_stock,
            payload.reason,
        )
        return product

    def deactivate(self, product_id: int) -> Product:
        """Soft delete: catalogue items referenced by sales are never removed."""
        product = self.get(product_id)
        product.is_active = False
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product_id: int) -> None:
        """Hard delete, allowed only when the product has no sales history."""
        product = self.get(product_id)
        if self.sale_repo.product_has_sales(product_id):
            raise ConflictError(
                "This product appears in past sales and cannot be deleted. "
                "Deactivate it instead to preserve history."
            )
        self.repo.delete(product)
        self.db.commit()
        logger.info("Deleted product %s", product.sku)

    # -- helpers ----------------------------------------------------------
    def _record_movement(
        self,
        *,
        product: Product,
        quantity: int,
        previous_stock: int,
        new_stock: int,
        transaction_type: TransactionType,
        reference: Optional[str],
        notes: Optional[str],
        user_id: Optional[int],
    ) -> None:
        self.inventory_repo.create(
            product_id=product.id,
            transaction_type=transaction_type,
            quantity=quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reference=reference,
            notes=notes,
            created_by=user_id,
        )
