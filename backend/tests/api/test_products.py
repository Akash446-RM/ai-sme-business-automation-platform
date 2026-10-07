"""Product endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest_helpers import API, create_product

pytestmark = pytest.mark.api


def test_create_product(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers)
    assert product["sku"] == "SKU-MOUSE-001"
    assert product["stock"] == 50
    assert product["stock_status"] == "healthy"
    assert product["margin_per_unit"] == "199.00"


def test_create_product_requires_auth(client: TestClient) -> None:
    response = client.post(
        f"{API}/products",
        json={
            "name": "No Auth",
            "sku": "X1",
            "category": "Misc",
            "cost_price": "1.00",
            "selling_price": "2.00",
        },
    )
    assert response.status_code == 401


def test_duplicate_sku_conflicts(client: TestClient, auth_headers: dict) -> None:
    create_product(client, auth_headers)
    response = client.post(
        f"{API}/products",
        headers=auth_headers,
        json={
            "name": "Another",
            "sku": "SKU-MOUSE-001",
            "category": "Electronics",
            "cost_price": "10.00",
            "selling_price": "20.00",
        },
    )
    assert response.status_code == 409


def test_selling_price_below_cost_rejected(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        f"{API}/products",
        headers=auth_headers,
        json={
            "name": "Loss Maker",
            "sku": "SKU-LOSS",
            "category": "Misc",
            "cost_price": "100.00",
            "selling_price": "50.00",
        },
    )
    assert response.status_code == 422


def test_opening_stock_creates_ledger_entry(
    client: TestClient, auth_headers: dict, db_session
) -> None:
    from app.models.inventory_transaction import InventoryTransaction

    product = create_product(client, auth_headers, stock=25)
    rows = (
        db_session.query(InventoryTransaction)
        .filter(InventoryTransaction.product_id == product["id"])
        .all()
    )
    assert len(rows) == 1
    assert rows[0].quantity == 25
    assert rows[0].previous_stock == 0
    assert rows[0].new_stock == 25
    assert str(rows[0].transaction_type) == "initial"


def test_stock_status_transitions(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=5, reorder_level=10)
    assert product["stock_status"] == "low"

    zero = create_product(client, auth_headers, sku="SKU-ZERO", stock=0)
    assert zero["stock_status"] == "out_of_stock"

    over = create_product(
        client, auth_headers, sku="SKU-OVER", stock=500, reorder_level=10, max_stock_level=100
    )
    assert over["stock_status"] == "overstock"


def test_list_filters_and_pagination(client: TestClient, auth_headers: dict) -> None:
    for index in range(5):
        create_product(
            client,
            auth_headers,
            name=f"Item {index}",
            sku=f"SKU-{index}",
            category="Grocery" if index % 2 == 0 else "Electronics",
            stock=index,
            reorder_level=2,
        )

    page = client.get(
        f"{API}/products", headers=auth_headers, params={"page_size": 2}
    ).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["total_pages"] == 3
    assert page["has_next"] is True

    grocery = client.get(
        f"{API}/products", headers=auth_headers, params={"category": "Grocery"}
    ).json()
    assert grocery["total"] == 3

    out_of_stock = client.get(
        f"{API}/products", headers=auth_headers, params={"out_of_stock_only": True}
    ).json()
    assert out_of_stock["total"] == 1


def test_search_matches_name_and_sku(client: TestClient, auth_headers: dict) -> None:
    create_product(client, auth_headers, name="Bluetooth Keyboard", sku="SKU-KB-1")
    results = client.get(
        f"{API}/products/search", headers=auth_headers, params={"q": "keyboard"}
    ).json()
    assert len(results) == 1
    assert results[0]["name"] == "Bluetooth Keyboard"


def test_update_product(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers)
    response = client.put(
        f"{API}/products/{product['id']}",
        headers=auth_headers,
        json={"selling_price": "599.00", "reorder_level": 20},
    )
    assert response.status_code == 200
    assert response.json()["selling_price"] == "599.00"
    assert response.json()["reorder_level"] == 20


def test_adjust_stock_up_and_down(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=10)

    up = client.post(
        f"{API}/products/{product['id']}/adjust-stock",
        headers=auth_headers,
        json={"quantity": 15, "reason": "Supplier delivery received"},
    )
    assert up.status_code == 200
    assert up.json()["stock"] == 25

    down = client.post(
        f"{API}/products/{product['id']}/adjust-stock",
        headers=auth_headers,
        json={"quantity": -5, "reason": "Damaged units written off"},
    )
    assert down.json()["stock"] == 20


def test_adjust_stock_cannot_go_negative(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=3)
    response = client.post(
        f"{API}/products/{product['id']}/adjust-stock",
        headers=auth_headers,
        json={"quantity": -10, "reason": "Bad count"},
    )
    assert response.status_code == 422


def test_delete_product_without_sales(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers)
    assert client.delete(f"{API}/products/{product['id']}", headers=auth_headers).status_code == 200
    assert client.get(f"{API}/products/{product['id']}", headers=auth_headers).status_code == 404


def test_get_missing_product_returns_404(client: TestClient, auth_headers: dict) -> None:
    response = client.get(f"{API}/products/9999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
