"""Generate a realistic synthetic business history.

The goal is not merely to fill tables: the generated data must contain the
patterns a forecasting model is supposed to learn - trend, annual seasonality,
weekday effects, festival spikes, per product popularity, price sensitivity,
customer loyalty and deliberate demand shifts. Without those patterns any ML
evaluation would be meaningless.

Usage:
    python -m app.scripts.seed_data                 # full dataset
    python -m app.scripts.seed_data --scale small   # fast development dataset
    python -m app.scripts.seed_data --reset         # wipe business data first
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models.alert import Alert
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.enums import PaymentMethod, TransactionType, UserRole
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.user import User
from app.scripts.catalog_data import (
    BRANDS,
    CATEGORY_PROFILES,
    CATEGORY_VARIANTS,
    CITIES,
    EMPLOYEE_ROLES,
    FESTIVAL_WINDOWS,
    FIRST_NAMES,
    LAST_NAMES,
    PRODUCT_NOUNS,
    GENERIC_VARIANTS,
    SUPPLIERS,
)

CENTS = Decimal("0.01")
BATCH_SIZE = 5_000

SCALES = {
    "small": {"products": 150, "customers": 100, "employees": 12, "months": 12},
    "full": {"products": 500, "customers": 300, "employees": 20, "months": 24},
}


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass
class ProductProfile:
    """Simulation parameters attached to a generated product."""

    product: Product
    popularity: float
    seasonality: str
    basket_affinity: float
    trend: float = 0.0
    shift_start: Optional[date] = None
    shift_factor: float = 1.0
    price_elasticity: float = -0.8
    units_sold: int = 0
    daily_history: List[int] = field(default_factory=list)


class BusinessSimulator:
    """Creates a coherent, pattern rich sales history."""

    def __init__(self, db: Session, scale: str, seed: int = 20260809) -> None:
        self.db = db
        self.config = SCALES[scale]
        self.random = random.Random(seed)
        self.profiles: List[ProductProfile] = []
        self.customers: List[Customer] = []
        self.employees: List[Employee] = []
        self.customer_weights: List[float] = []
        self.employee_weights: List[float] = []

    # -- master data ------------------------------------------------------
    def create_admin_user(self) -> None:
        existing = self.db.execute(select(func.count(User.id))).scalar_one()
        if existing:
            print("[skip] users already present")
            return
        self.db.add_all(
            [
                User(
                    email="owner@smeplatform.com",
                    full_name="Business Owner",
                    hashed_password=hash_password("Owner@12345"),
                    role=UserRole.OWNER,
                ),
                User(
                    email="manager@smeplatform.com",
                    full_name="Store Manager",
                    hashed_password=hash_password("Manager@12345"),
                    role=UserRole.MANAGER,
                ),
                User(
                    email="staff@smeplatform.com",
                    full_name="Sales Staff",
                    hashed_password=hash_password("Staff@12345"),
                    role=UserRole.STAFF,
                ),
            ]
        )
        self.db.commit()
        print("[ok] created 3 demo accounts (owner / manager / staff)")

    def create_products(self) -> None:
        target = self.config["products"]
        categories = list(CATEGORY_PROFILES)
        products: List[Product] = []
        used_names: set[str] = set()
        sequence = 1

        # Distribute products across categories proportionally to popularity.
        weights = [CATEGORY_PROFILES[category]["popularity"] for category in categories]
        total_weight = sum(weights)
        allocation = {
            category: max(6, int(target * weight / total_weight))
            for category, weight in zip(categories, weights)
        }
        # Trim or pad to hit the exact target.
        while sum(allocation.values()) > target:
            allocation[max(allocation, key=allocation.get)] -= 1
        while sum(allocation.values()) < target:
            allocation[min(allocation, key=allocation.get)] += 1

        for category, count in allocation.items():
            profile = CATEGORY_PROFILES[category]
            low_price, high_price = profile["price_range"]
            nouns = PRODUCT_NOUNS[category]
            variants = CATEGORY_VARIANTS.get(category, GENERIC_VARIANTS)

            for _ in range(count):
                for _attempt in range(30):
                    name = (
                        f"{self.random.choice(BRANDS)} "
                        f"{self.random.choice(nouns)} "
                        f"{self.random.choice(variants)}"
                    )
                    if name not in used_names:
                        break
                used_names.add(name)

                # Log-normal pricing keeps most items affordable with a few premium SKUs.
                price_factor = min(max(self.random.lognormvariate(0, 0.55), 0.25), 4.0)
                selling = low_price + (high_price - low_price) * min(price_factor / 4.0, 1.0)
                selling = max(low_price, round(selling, 0))
                margin = self.random.uniform(*profile["margin"])
                cost = round(selling * (1 - margin), 2)

                # Popularity is log-normal: a few bestsellers, a long tail.
                popularity = profile["popularity"] * self.random.lognormvariate(0, 0.85)

                reorder_level = max(5, int(popularity * self.random.uniform(6, 14)))
                opening_stock = int(reorder_level * self.random.uniform(1.5, 6.0))

                product = Product(
                    name=name,
                    category=category,
                    sku=f"SKU-{sequence:05d}",
                    barcode=f"890{sequence:010d}",
                    description=f"{category} item stocked for regular retail demand.",
                    cost_price=money(cost),
                    selling_price=money(selling),
                    stock=opening_stock,
                    reorder_level=reorder_level,
                    max_stock_level=int(reorder_level * self.random.uniform(8, 14)),
                    supplier=self.random.choice(SUPPLIERS),
                    lead_time_days=self.random.choice([2, 3, 4, 5, 5, 7, 7, 10, 14]),
                    is_active=True,
                )
                products.append(product)
                self.profiles.append(
                    ProductProfile(
                        product=product,
                        popularity=popularity,
                        seasonality=profile["seasonality"],
                        basket_affinity=profile["basket_affinity"],
                        price_elasticity=self.random.uniform(-1.4, -0.3),
                    )
                )
                sequence += 1

        self.db.add_all(products)
        self.db.commit()

        # Deliberate demand shifts on ~6% of products so trend detectors and
        # forecasts have genuine signal to find.
        shift_count = max(4, int(len(self.profiles) * 0.06))
        for profile in self.random.sample(self.profiles, shift_count):
            profile.shift_factor = self.random.choice([0.35, 0.45, 1.9, 2.4, 3.0])
            profile.shift_start = None  # assigned once the date range is known

        # Gentle long term trend per product.
        for profile in self.profiles:
            profile.trend = self.random.uniform(-0.25, 0.45)

        print(f"[ok] created {len(products)} products across {len(allocation)} categories")

    def create_customers(self) -> None:
        target = self.config["customers"]
        customers: List[Customer] = []
        used_phones: set[str] = set()

        for index in range(1, target + 1):
            name = f"{self.random.choice(FIRST_NAMES)} {self.random.choice(LAST_NAMES)}"
            while True:
                phone = f"9{self.random.randint(100000000, 999999999)}"
                if phone not in used_phones:
                    used_phones.add(phone)
                    break
            slug = name.lower().replace(" ", ".")
            customers.append(
                Customer(
                    customer_code=f"CUST{index:05d}",
                    name=name,
                    phone=phone,
                    email=f"{slug}{index}@example.com",
                    city=self.random.choice(CITIES),
                    address=f"{self.random.randint(1, 400)}, {self.random.choice(CITIES)} Main Road",
                    is_active=True,
                )
            )

        self.db.add_all(customers)
        self.db.commit()
        self.customers = customers

        # Pareto style loyalty: a minority of customers drive most transactions.
        self.customer_weights = [
            self.random.lognormvariate(0, 1.1) for _ in self.customers
        ]
        print(f"[ok] created {len(customers)} customers")

    def create_employees(self) -> None:
        target = self.config["employees"]
        employees: List[Employee] = []
        used_phones: set[str] = set()
        index = 1

        slots: List[Tuple[str, str]] = []
        for role, department, count in EMPLOYEE_ROLES:
            slots.extend([(role, department)] * count)
        while len(slots) < target:
            slots.append(("Sales Executive", "Sales"))
        slots = slots[:target]

        for role, department in slots:
            name = f"{self.random.choice(FIRST_NAMES)} {self.random.choice(LAST_NAMES)}"
            while True:
                phone = f"8{self.random.randint(100000000, 999999999)}"
                if phone not in used_phones:
                    used_phones.add(phone)
                    break
            employees.append(
                Employee(
                    employee_code=f"EMP{index:04d}",
                    name=name,
                    role=role,
                    department=department,
                    phone=phone,
                    email=f"{name.lower().replace(' ', '.')}{index}@smeplatform.com",
                    hired_on=date.today() - timedelta(days=self.random.randint(120, 1800)),
                    is_active=True,
                )
            )
            index += 1

        self.db.add_all(employees)
        self.db.commit()
        self.employees = employees
        # Billing staff handle more transactions than back office roles.
        self.employee_weights = [
            3.0 if employee.role in {"Cashier", "Sales Executive"} else 0.6
            for employee in self.employees
        ]
        print(f"[ok] created {len(employees)} employees")

    # -- demand model -----------------------------------------------------
    def _seasonal_multiplier(self, profile: ProductProfile, day: date) -> float:
        """Annual seasonality shaped by the product's category profile."""
        day_of_year = day.timetuple().tm_yday
        angle = 2 * math.pi * day_of_year / 365.25

        if profile.seasonality == "summer":
            return 1.0 + 0.35 * math.sin(angle - math.pi / 2 + 0.9)
        if profile.seasonality == "winter":
            return 1.0 + 0.30 * math.cos(angle)
        if profile.seasonality == "school":
            # Peaks around the June academic intake and again in November.
            return 1.0 + 0.45 * math.exp(-(((day.month - 6) ** 2) / 2.0)) + 0.2 * math.exp(
                -(((day.month - 11) ** 2) / 2.0)
            )
        if profile.seasonality == "festival":
            return 1.0 + 0.15 * math.sin(angle)
        return 1.0 + 0.08 * math.sin(angle)

    @staticmethod
    def _festival_multiplier(day: date) -> float:
        multiplier = 1.0
        for month, target_day, spread, lift in FESTIVAL_WINDOWS:
            try:
                festival = date(day.year, month, target_day)
            except ValueError:  # pragma: no cover - guards odd dates
                continue
            distance = abs((day - festival).days)
            if distance <= spread:
                multiplier *= 1.0 + (lift - 1.0) * (1 - distance / (spread + 1))
        return multiplier

    @staticmethod
    def _weekday_multiplier(day: date) -> float:
        # Mon..Sun - retail footfall rises towards the weekend.
        return [0.85, 0.88, 0.92, 1.00, 1.18, 1.42, 1.25][day.weekday()]

    def _daily_transaction_count(self, day: date, day_index: int, total_days: int) -> int:
        """Number of bills raised on a given day."""
        base = 28 if self.config["products"] >= 400 else 14
        growth = 1.0 + 0.35 * (day_index / max(total_days - 1, 1))  # business grows over time
        multiplier = (
            growth
            * self._weekday_multiplier(day)
            * self._festival_multiplier(day)
            * (1.0 + 0.10 * math.sin(2 * math.pi * day.timetuple().tm_yday / 365.25))
        )
        count = self.random.gauss(base * multiplier, base * 0.18)
        return max(3, int(round(count)))

    def _product_weight(self, profile: ProductProfile, day: date, progress: float) -> float:
        """Relative chance of a product appearing in a basket on a given day."""
        weight = profile.popularity
        weight *= 1.0 + profile.trend * progress
        weight *= self._seasonal_multiplier(profile, day)
        if profile.shift_start and day >= profile.shift_start:
            weight *= profile.shift_factor
        # Cheaper items are bought more often (simple elasticity effect).
        price = float(profile.product.selling_price)
        weight *= (max(price, 10) / 250) ** profile.price_elasticity * 2.2
        return max(weight, 0.0005)

    # -- sales generation -------------------------------------------------
    def generate_sales(self) -> None:
        months = self.config["months"]
        end_date = date.today()
        start_date = end_date - timedelta(days=int(months * 30.44))
        total_days = (end_date - start_date).days + 1

        # Demand shifts begin in the final third of the history.
        shift_window_start = start_date + timedelta(days=int(total_days * 0.66))
        for profile in self.profiles:
            if profile.shift_factor != 1.0:
                profile.shift_start = shift_window_start + timedelta(
                    days=self.random.randint(0, max(int(total_days * 0.2), 1))
                )

        gst_rate = Decimal(str(settings.gst_rate))
        stock_levels: Dict[int, int] = {
            profile.product.id: profile.product.stock for profile in self.profiles
        }
        # Start the history with generous stock; realistic levels are set at the end.
        for product_id in stock_levels:
            stock_levels[product_id] = 10**6

        sale_rows: List[dict] = []
        item_rows: List[dict] = []
        movement_rows: List[dict] = []
        sale_id = 1
        bill_sequence: Dict[str, int] = {}

        profiles_by_id = {profile.product.id: profile for profile in self.profiles}
        product_ids = [profile.product.id for profile in self.profiles]

        print(
            f"[..] simulating {total_days} days of trading "
            f"({start_date} to {end_date})"
        )

        for day_index in range(total_days):
            day = start_date + timedelta(days=day_index)
            progress = day_index / max(total_days - 1, 1)

            weights = [
                self._product_weight(profiles_by_id[pid], day, progress) for pid in product_ids
            ]
            transactions = self._daily_transaction_count(day, day_index, total_days)

            for _ in range(transactions):
                basket_size = min(
                    max(1, int(self.random.lognormvariate(0.62, 0.62))), 9
                )
                chosen = self._choose_products(product_ids, weights, basket_size)

                customer = self._weighted_choice(self.customers, self.customer_weights)
                employee = self._weighted_choice(self.employees, self.employee_weights)

                hour = self._sale_hour()
                sale_time = datetime.combine(day, datetime.min.time()) + timedelta(
                    hours=hour, minutes=self.random.randint(0, 59)
                )

                subtotal = Decimal("0.00")
                lines: List[dict] = []
                for product_id in chosen:
                    profile = profiles_by_id[product_id]
                    product = profile.product
                    quantity = self._quantity_for(profile)
                    if stock_levels[product_id] < quantity:
                        continue

                    unit_price = product.selling_price
                    gross = money(unit_price * quantity)
                    # Occasional line level promotion.
                    discount = (
                        money(gross * Decimal(str(self.random.choice([0.05, 0.10, 0.15]))))
                        if self.random.random() < 0.12
                        else Decimal("0.00")
                    )
                    line_total = money(gross - discount)
                    subtotal += line_total

                    previous_stock = stock_levels[product_id]
                    new_stock = previous_stock - quantity
                    stock_levels[product_id] = new_stock
                    profile.units_sold += quantity

                    lines.append(
                        {
                            "sale_id": sale_id,
                            "product_id": product_id,
                            "product_name": product.name,
                            "quantity": quantity,
                            "unit_price": unit_price,
                            "unit_cost": product.cost_price,
                            "discount_amount": discount,
                            "line_total": line_total,
                        }
                    )
                    movement_rows.append(
                        {
                            "product_id": product_id,
                            "transaction_type": TransactionType.SALE,
                            "quantity": -quantity,
                            "previous_stock": previous_stock,
                            "new_stock": new_stock,
                            "reference": None,  # filled in below with the bill number
                            "notes": None,
                            "created_by": None,
                            "created_at": sale_time,
                            "_sale_id": sale_id,
                        }
                    )

                if not lines:
                    continue

                bill_prefix = f"INV{day:%Y%m}-"
                bill_sequence[bill_prefix] = bill_sequence.get(bill_prefix, 0) + 1
                bill_no = f"{bill_prefix}{bill_sequence[bill_prefix]:05d}"

                bill_discount = (
                    money(subtotal * Decimal("0.05"))
                    if self.random.random() < 0.08
                    else Decimal("0.00")
                )
                taxable = money(subtotal - bill_discount)
                gst_amount = money(taxable * gst_rate / Decimal("100"))

                sale_rows.append(
                    {
                        "id": sale_id,
                        "bill_no": bill_no,
                        "customer_id": customer.id,
                        "employee_id": employee.id,
                        "subtotal": money(subtotal),
                        "discount_amount": bill_discount,
                        "taxable_amount": taxable,
                        "gst_rate": gst_rate,
                        "gst_amount": gst_amount,
                        "total_amount": money(taxable + gst_amount),
                        "payment_method": self._payment_method(),
                        "notes": None,
                        "sale_date": sale_time,
                        "created_at": sale_time,
                        "updated_at": sale_time,
                    }
                )
                item_rows.extend(lines)
                for movement in movement_rows:
                    if movement.get("_sale_id") == sale_id and movement["reference"] is None:
                        movement["reference"] = bill_no
                        movement["notes"] = f"Sold on bill {bill_no}"
                sale_id += 1

            if len(sale_rows) >= BATCH_SIZE:
                self._flush(sale_rows, item_rows, movement_rows)
                sale_rows, item_rows, movement_rows = [], [], []
                print(f"     ... {day} ({sale_id - 1} bills so far)")

        self._flush(sale_rows, item_rows, movement_rows)
        print(f"[ok] generated {sale_id - 1} sales")

        self._finalise_stock(stock_levels)

    def _choose_products(
        self, product_ids: List[int], weights: List[float], basket_size: int
    ) -> List[int]:
        chosen: List[int] = []
        attempts = 0
        while len(chosen) < basket_size and attempts < basket_size * 4:
            picked = self.random.choices(product_ids, weights=weights, k=1)[0]
            if picked not in chosen:
                chosen.append(picked)
            attempts += 1
        return chosen

    @staticmethod
    def _weighted_choice(items: List, weights: List[float]):
        return random.choices(items, weights=weights, k=1)[0]

    def _quantity_for(self, profile: ProductProfile) -> int:
        """Cheap fast movers sell in multiples; expensive goods sell singly."""
        price = float(profile.product.selling_price)
        if price < 100:
            return self.random.choices([1, 2, 3, 4, 5, 6], weights=[25, 25, 20, 15, 10, 5])[0]
        if price < 600:
            return self.random.choices([1, 2, 3], weights=[60, 30, 10])[0]
        if price < 3000:
            return self.random.choices([1, 2], weights=[85, 15])[0]
        return 1

    def _sale_hour(self) -> int:
        # Two footfall peaks: late morning and early evening.
        return self.random.choices(
            list(range(9, 22)),
            weights=[4, 7, 9, 8, 6, 5, 6, 8, 11, 13, 11, 7, 3],
        )[0]

    def _payment_method(self) -> PaymentMethod:
        return self.random.choices(
            [
                PaymentMethod.UPI,
                PaymentMethod.CASH,
                PaymentMethod.CARD,
                PaymentMethod.CREDIT,
            ],
            weights=[45, 30, 20, 5],
        )[0]

    def _flush(
        self, sale_rows: List[dict], item_rows: List[dict], movement_rows: List[dict]
    ) -> None:
        if not sale_rows:
            return
        for movement in movement_rows:
            movement.pop("_sale_id", None)
        self.db.execute(Sale.__table__.insert(), sale_rows)
        self.db.execute(SaleItem.__table__.insert(), item_rows)
        self.db.execute(InventoryTransaction.__table__.insert(), movement_rows)
        self.db.commit()

    def _finalise_stock(self, stock_levels: Dict[int, int]) -> None:
        """Set closing stock to realistic levels driven by recent demand.

        The simulation runs with effectively unlimited stock so demand is never
        censored. Afterwards each product is given a closing position based on
        its true recent sales rate, producing a believable mix of healthy, low
        and out of stock items.
        """
        recent_start = datetime.now() - timedelta(days=30)
        rows = self.db.execute(
            select(SaleItem.product_id, func.sum(SaleItem.quantity))
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(Sale.sale_date >= recent_start)
            .group_by(SaleItem.product_id)
        ).all()
        recent_units = {int(row[0]): int(row[1] or 0) for row in rows}

        updates = []
        for profile in self.profiles:
            product = profile.product
            velocity = recent_units.get(product.id, 0) / 30.0
            reorder_level = max(5, int(round(velocity * product.lead_time_days * 1.6)) or 5)

            roll = self.random.random()
            if roll < 0.05:
                closing = 0                                        # out of stock
            elif roll < 0.20:
                closing = int(reorder_level * self.random.uniform(0.2, 0.95))  # low
            elif roll < 0.90:
                closing = int(reorder_level * self.random.uniform(1.6, 5.0))   # healthy
            else:
                closing = int(reorder_level * self.random.uniform(9, 16))      # overstock

            updates.append(
                {
                    "product_id": product.id,
                    "stock": max(closing, 0),
                    "reorder_level": reorder_level,
                    "max_stock_level": max(int(reorder_level * 8), 20),
                }
            )

        self.db.execute(
            text(
                "UPDATE products SET stock = :stock, reorder_level = :reorder_level, "
                "max_stock_level = :max_stock_level WHERE id = :product_id"
            ),
            updates,
        )
        self.db.commit()

        # Record the closing position so the ledger reconciles with stock on hand.
        now = datetime.now()
        self.db.execute(
            InventoryTransaction.__table__.insert(),
            [
                {
                    "product_id": row["product_id"],
                    "transaction_type": TransactionType.PURCHASE,
                    "quantity": row["stock"],
                    "previous_stock": 0,
                    "new_stock": row["stock"],
                    "reference": "OPENING-BALANCE",
                    "notes": "Closing stock position after historical simulation",
                    "created_by": None,
                    "created_at": now,
                }
                for row in updates
                if row["stock"] > 0
            ],
        )
        self.db.commit()
        print("[ok] closing stock levels and reorder points calibrated to demand")


def reset_business_data(db: Session) -> None:
    """Remove generated business data, leaving user accounts intact."""
    db.execute(delete(Alert))
    db.execute(delete(InventoryTransaction))
    db.execute(delete(SaleItem))
    db.execute(delete(Sale))
    db.execute(delete(Product))
    db.execute(delete(Customer))
    db.execute(delete(Employee))
    db.commit()
    print("[ok] existing business data cleared")


def summarise(db: Session) -> None:
    counts = {
        "products": db.execute(select(func.count(Product.id))).scalar_one(),
        "customers": db.execute(select(func.count(Customer.id))).scalar_one(),
        "employees": db.execute(select(func.count(Employee.id))).scalar_one(),
        "sales": db.execute(select(func.count(Sale.id))).scalar_one(),
        "sale_items": db.execute(select(func.count(SaleItem.id))).scalar_one(),
        "inventory_transactions": db.execute(
            select(func.count(InventoryTransaction.id))
        ).scalar_one(),
    }
    revenue = db.execute(select(func.coalesce(func.sum(Sale.total_amount), 0))).scalar_one()
    first = db.execute(select(func.min(Sale.sale_date))).scalar_one()
    last = db.execute(select(func.max(Sale.sale_date))).scalar_one()

    print("\n" + "=" * 62)
    print("SEED SUMMARY")
    print("=" * 62)
    for label, value in counts.items():
        print(f"  {label:<24} {value:>12,}")
    print(f"  {'total revenue':<24} {float(revenue):>12,.2f}")
    print(f"  {'history':<24} {first} -> {last}")
    print("=" * 62)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed realistic SME business data")
    parser.add_argument("--scale", choices=list(SCALES), default="full")
    parser.add_argument("--reset", action="store_true", help="clear business data first")
    parser.add_argument("--seed", type=int, default=20260809, help="random seed")
    args = parser.parse_args()

    print(f"Database : {settings.db_name}")
    print(f"Scale    : {args.scale} -> {SCALES[args.scale]}")

    with SessionLocal() as db:
        if args.reset:
            reset_business_data(db)

        existing_products = db.execute(select(func.count(Product.id))).scalar_one()
        if existing_products:
            print(
                f"[abort] {existing_products} products already exist. "
                "Re-run with --reset to regenerate."
            )
            return 1

        simulator = BusinessSimulator(db, args.scale, seed=args.seed)
        simulator.create_admin_user()
        simulator.create_products()
        simulator.create_customers()
        simulator.create_employees()
        simulator.generate_sales()
        summarise(db)

    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
