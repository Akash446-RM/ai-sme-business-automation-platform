"""ORM models.

Importing this package registers every table on the shared declarative Base,
which is what Alembic autogeneration and ``Base.metadata`` rely on.
"""

from app.models.alert import Alert
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    MovementClass,
    PaymentMethod,
    StockStatus,
    TransactionType,
    UserRole,
)
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.user import User

__all__ = [
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "AlertType",
    "Customer",
    "Employee",
    "InventoryTransaction",
    "MovementClass",
    "PaymentMethod",
    "Product",
    "Sale",
    "SaleItem",
    "StockStatus",
    "TransactionType",
    "User",
    "UserRole",
]
