"""Inventory intelligence endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest_helpers import API, create_product, create_sale

pytestmark = pytest.mark.api


def test_overview_counts_stock_states(client: TestClient, auth_headers: dict) -> None:
    create_product(client, auth_headers, sku="SKU-OK", stock=100, reorder_level=10)
    create_product(client, auth_headers, sku="SKU-LOW", stock=5, reorder_level=10)
    create_product(client, auth_headers, sku="SKU-OUT", stock=0, reorder_level=10)

    overview = client.get(f"{API}/inventory/overview", headers=auth_headers).json()
    assert overview["total_products"] == 3
    assert overview["low_stock_count"] == 1
    assert overview["out_of_stock_count"] == 1
    assert overview["healthy_count"] == 1
    assert overview["total_units"] == 105


def test_stock_list_reports_velocity(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=100)
    create_sale(client, auth_headers, product_id=product["id"], quantity=30)

    page = client.get(f"{API}/inventory/stock", headers=auth_headers).json()
    item = page["items"][0]
    assert item["units_sold_30d"] == 30
    assert item["daily_velocity"] == pytest.approx(1.0, abs=0.01)
    assert item["days_of_cover"] == pytest.approx(70.0, abs=0.5)
    assert item["movement_class"] == "fast_moving"


def test_stock_filter_by_status(client: TestClient, auth_headers: dict) -> None:
    create_product(client, auth_headers, sku="SKU-A", stock=2, reorder_level=10)
    create_product(client, auth_headers, sku="SKU-B", stock=80, reorder_level=10)

    low = client.get(
        f"{API}/inventory/stock", headers=auth_headers, params={"status": "low"}
    ).json()
    assert low["total"] == 1
    assert low["items"][0]["sku"] == "SKU-A"


def test_recommendation_is_explainable(client: TestClient, auth_headers: dict) -> None:
    product = create_product(
        client, auth_headers, name="Wireless Mouse", stock=42, reorder_level=10
    )
    create_sale(client, auth_headers, product_id=product["id"], quantity=30)

    body = client.get(
        f"{API}/inventory/recommendations/{product['id']}",
        headers=auth_headers,
        params={"horizon_days": 7},
    ).json()

    assert body["product_id"] == product["id"]
    assert body["forecast_horizon_days"] == 7
    assert body["daily_velocity"] > 0
    assert body["reasons"], "recommendation must explain itself"
    assert "formula" in body["evidence"]
    assert body["evidence"]["units_sold_last_30_days"] == 30
    assert body["forecast_source"] == "statistical_baseline"


def test_recommendation_quantity_matches_formula(
    client: TestClient, auth_headers: dict
) -> None:
    product = create_product(client, auth_headers, stock=12, reorder_level=10)
    create_sale(client, auth_headers, product_id=product["id"], quantity=30)

    body = client.get(
        f"{API}/inventory/recommendations/{product['id']}",
        headers=auth_headers,
        params={"horizon_days": 7},
    ).json()

    expected = max(
        0, round(body["forecast_demand"] + body["safety_stock"] - body["current_stock"])
    )
    assert body["recommended_quantity"] == expected
    assert body["urgency"] in {"critical", "high", "medium", "low", "none"}


def test_no_reorder_needed_when_stock_is_ample(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=10_000, reorder_level=10)
    create_sale(client, auth_headers, product_id=product["id"], quantity=5)

    body = client.get(
        f"{API}/inventory/recommendations/{product['id']}", headers=auth_headers
    ).json()
    assert body["recommended_quantity"] == 0
    assert body["urgency"] == "none"


def test_recommendations_list_prioritises_urgency(
    client: TestClient, auth_headers: dict
) -> None:
    urgent = create_product(client, auth_headers, sku="SKU-URGENT", stock=1, reorder_level=20)
    create_sale(client, auth_headers, product_id=urgent["id"], quantity=1)
    create_product(client, auth_headers, sku="SKU-FINE", stock=900, reorder_level=5)

    items = client.get(f"{API}/inventory/recommendations", headers=auth_headers).json()
    assert items
    assert items[0]["sku"] == "SKU-URGENT"


def test_movement_analysis(client: TestClient, auth_headers: dict) -> None:
    fast = create_product(client, auth_headers, sku="SKU-FAST", stock=200)
    create_product(client, auth_headers, sku="SKU-NEVER", stock=50)
    create_sale(client, auth_headers, product_id=fast["id"], quantity=60)

    body = client.get(f"{API}/inventory/movement", headers=auth_headers).json()
    assert body["fast_moving"][0]["product_id"] == fast["id"]
    assert any(item["name"] for item in body["never_sold"])


def test_valuation_by_category(client: TestClient, auth_headers: dict) -> None:
    create_product(
        client,
        auth_headers,
        sku="SKU-V1",
        category="Grocery",
        cost_price="10.00",
        selling_price="15.00",
        stock=100,
    )
    body = client.get(f"{API}/inventory/valuation", headers=auth_headers).json()
    grocery = next(row for row in body if row["category"] == "Grocery")
    assert grocery["cost_value"] == "1000.00"
    assert grocery["retail_value"] == "1500.00"
    assert grocery["potential_margin"] == "500.00"


def test_transaction_ledger_records_sale(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=40)
    create_sale(client, auth_headers, product_id=product["id"], quantity=6)

    page = client.get(
        f"{API}/inventory/transactions",
        headers=auth_headers,
        params={"product_id": product["id"], "transaction_type": "sale"},
    ).json()
    assert page["total"] == 1
    row = page["items"][0]
    assert row["quantity"] == -6
    assert row["previous_stock"] == 40
    assert row["new_stock"] == 34
    assert row["product_sku"] == product["sku"]


def test_inventory_requires_authentication(client: TestClient) -> None:
    assert client.get(f"{API}/inventory/overview").status_code == 401
