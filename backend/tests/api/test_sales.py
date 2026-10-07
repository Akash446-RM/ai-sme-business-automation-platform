"""Sales workflow endpoint tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tests.conftest_helpers import (
    API,
    create_customer,
    create_employee,
    create_product,
    create_sale,
)

pytestmark = pytest.mark.api


def test_sale_calculates_totals_correctly(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, selling_price="500.00", stock=20)
    response = create_sale(client, auth_headers, product_id=product["id"], quantity=2)
    assert response.status_code == 201, response.text

    sale = response.json()["sale"]
    # 2 x 500 = 1000 subtotal, no discount, 18% GST -> 1180
    assert Decimal(sale["subtotal"]) == Decimal("1000.00")
    assert Decimal(sale["discount_amount"]) == Decimal("0.00")
    assert Decimal(sale["taxable_amount"]) == Decimal("1000.00")
    assert Decimal(sale["gst_amount"]) == Decimal("180.00")
    assert Decimal(sale["total_amount"]) == Decimal("1180.00")
    assert sale["bill_no"].startswith("INV")


def test_sale_applies_bill_and_line_discounts(client: TestClient, auth_headers: dict) -> None:
    product = create_product(
        client, auth_headers, cost_price="60.00", selling_price="100.00", stock=50
    )
    response = client.post(
        f"{API}/sales",
        headers=auth_headers,
        json={
            "items": [
                {"product_id": product["id"], "quantity": 10, "discount_amount": "50.00"}
            ],
            "discount_amount": "150.00",
            "gst_rate": "10.00",
        },
    )
    assert response.status_code == 201
    sale = response.json()["sale"]
    # line: 1000 - 50 = 950 subtotal; bill discount 150 -> taxable 800; GST 10% -> 880
    assert Decimal(sale["subtotal"]) == Decimal("950.00")
    assert Decimal(sale["taxable_amount"]) == Decimal("800.00")
    assert Decimal(sale["gst_amount"]) == Decimal("80.00")
    assert Decimal(sale["total_amount"]) == Decimal("880.00")


def test_sale_reduces_stock(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=30)
    create_sale(client, auth_headers, product_id=product["id"], quantity=7)
    refreshed = client.get(f"{API}/products/{product['id']}", headers=auth_headers).json()
    assert refreshed["stock"] == 23


def test_sale_writes_inventory_transaction(
    client: TestClient, auth_headers: dict, db_session
) -> None:
    from app.models.enums import TransactionType
    from app.models.inventory_transaction import InventoryTransaction

    product = create_product(client, auth_headers, stock=30)
    response = create_sale(client, auth_headers, product_id=product["id"], quantity=4)
    bill_no = response.json()["sale"]["bill_no"]

    row = (
        db_session.query(InventoryTransaction)
        .filter(
            InventoryTransaction.product_id == product["id"],
            InventoryTransaction.transaction_type == TransactionType.SALE,
        )
        .one()
    )
    assert row.quantity == -4
    assert row.previous_stock == 30
    assert row.new_stock == 26
    assert row.reference == bill_no


def test_sale_blocked_by_insufficient_stock(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=3)
    response = create_sale(client, auth_headers, product_id=product["id"], quantity=10)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "insufficient_stock"
    assert body["error"]["details"]["shortages"][0]["available"] == 3

    unchanged = client.get(f"{API}/products/{product['id']}", headers=auth_headers).json()
    assert unchanged["stock"] == 3


def test_failed_sale_is_fully_rolled_back(
    client: TestClient, auth_headers: dict, db_session
) -> None:
    """A multi-line sale where one line fails must not commit any part of it."""
    from app.models.sale import Sale

    good = create_product(client, auth_headers, sku="SKU-GOOD", stock=100)
    short = create_product(client, auth_headers, sku="SKU-SHORT", stock=1)

    response = client.post(
        f"{API}/sales",
        headers=auth_headers,
        json={
            "items": [
                {"product_id": good["id"], "quantity": 5},
                {"product_id": short["id"], "quantity": 50},
            ]
        },
    )
    assert response.status_code == 400
    assert db_session.query(Sale).count() == 0
    assert client.get(f"{API}/products/{good['id']}", headers=auth_headers).json()["stock"] == 100


def test_sale_reports_low_stock_alert(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=12, reorder_level=10)
    response = create_sale(client, auth_headers, product_id=product["id"], quantity=5)
    body = response.json()
    assert body["stock_updates"][0]["below_reorder_level"] is True
    assert any("reorder level" in alert for alert in body["alerts_raised"])


def test_sale_reports_out_of_stock_alert(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=5, reorder_level=2)
    response = create_sale(client, auth_headers, product_id=product["id"], quantity=5)
    assert any("out of stock" in alert for alert in response.json()["alerts_raised"])


def test_sale_with_unknown_product_returns_404(client: TestClient, auth_headers: dict) -> None:
    response = create_sale(client, auth_headers, product_id=4242, quantity=1)
    assert response.status_code == 404


def test_sale_rejects_duplicate_product_lines(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=50)
    response = client.post(
        f"{API}/sales",
        headers=auth_headers,
        json={
            "items": [
                {"product_id": product["id"], "quantity": 1},
                {"product_id": product["id"], "quantity": 2},
            ]
        },
    )
    assert response.status_code == 422


def test_sale_requires_at_least_one_item(client: TestClient, auth_headers: dict) -> None:
    response = client.post(f"{API}/sales", headers=auth_headers, json={"items": []})
    assert response.status_code == 422


def test_sale_rejects_inactive_product(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=10)
    client.post(f"{API}/products/{product['id']}/deactivate", headers=auth_headers)
    response = create_sale(client, auth_headers, product_id=product["id"], quantity=1)
    assert response.status_code == 422


def test_sale_links_customer_and_employee(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=10)
    customer = create_customer(client, auth_headers)
    employee = create_employee(client, auth_headers)
    response = create_sale(
        client,
        auth_headers,
        product_id=product["id"],
        quantity=1,
        customer_id=customer["id"],
        employee_id=employee["id"],
    )
    sale = response.json()["sale"]
    assert sale["customer_name"] == "Acme Retail"
    assert sale["employee_name"] == "Ravi Kumar"


def test_bill_numbers_are_sequential(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=100)
    first = create_sale(client, auth_headers, product_id=product["id"], quantity=1).json()
    second = create_sale(client, auth_headers, product_id=product["id"], quantity=1).json()
    assert first["sale"]["bill_no"] != second["sale"]["bill_no"]
    assert int(second["sale"]["bill_no"][-5:]) == int(first["sale"]["bill_no"][-5:]) + 1


def test_get_sale_detail_and_by_bill(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=10)
    created = create_sale(client, auth_headers, product_id=product["id"], quantity=3).json()
    sale_id = created["sale"]["id"]
    bill_no = created["sale"]["bill_no"]

    detail = client.get(f"{API}/sales/{sale_id}", headers=auth_headers).json()
    assert len(detail["items"]) == 1
    assert detail["items"][0]["quantity"] == 3

    by_bill = client.get(f"{API}/sales/by-bill/{bill_no}", headers=auth_headers).json()
    assert by_bill["id"] == sale_id


def test_void_sale_restores_stock(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=20)
    created = create_sale(client, auth_headers, product_id=product["id"], quantity=6).json()
    assert client.get(f"{API}/products/{product['id']}", headers=auth_headers).json()["stock"] == 14

    response = client.delete(f"{API}/sales/{created['sale']['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert client.get(f"{API}/products/{product['id']}", headers=auth_headers).json()["stock"] == 20


def test_sale_list_filters_by_customer(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=100)
    customer = create_customer(client, auth_headers)
    create_sale(client, auth_headers, product_id=product["id"], quantity=1, customer_id=customer["id"])
    create_sale(client, auth_headers, product_id=product["id"], quantity=1)

    page = client.get(
        f"{API}/sales", headers=auth_headers, params={"customer_id": customer["id"]}
    ).json()
    assert page["total"] == 1


def test_product_with_sales_cannot_be_deleted(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=10)
    create_sale(client, auth_headers, product_id=product["id"], quantity=1)
    response = client.delete(f"{API}/products/{product['id']}", headers=auth_headers)
    assert response.status_code == 409
