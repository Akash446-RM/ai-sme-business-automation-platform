"""End to end test of the platform's core value chain.

    create product
      -> create sale
      -> inventory decreases
      -> inventory transaction created
      -> low stock condition detected
      -> analytics updated
      -> forecast available
      -> reorder recommendation generated
      -> AI can explain the recommendation

If this test passes, the promise of the platform holds: data entered at one end
becomes an explainable business decision at the other.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest_helpers import API, create_customer, create_employee

pytestmark = pytest.mark.e2e


def test_sale_to_ai_explanation_chain(client: TestClient, auth_headers: dict) -> None:
    # 1. Create a product ------------------------------------------------
    product = client.post(
        f"{API}/products",
        headers=auth_headers,
        json={
            "name": "Wireless Mouse",
            "sku": "SKU-E2E-001",
            "category": "Electronics",
            "cost_price": "300.00",
            "selling_price": "500.00",
            "stock": 40,
            "reorder_level": 30,
            "lead_time_days": 5,
        },
    ).json()
    product_id = product["id"]
    assert product["stock"] == 40
    assert product["stock_status"] == "healthy"

    customer = create_customer(client, auth_headers)
    employee = create_employee(client, auth_headers)

    # 2. Create a sale ---------------------------------------------------
    sale_response = client.post(
        f"{API}/sales",
        headers=auth_headers,
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "items": [{"product_id": product_id, "quantity": 28}],
            "payment_method": "upi",
        },
    )
    assert sale_response.status_code == 201
    sale_body = sale_response.json()
    bill_no = sale_body["sale"]["bill_no"]

    # 3. Inventory decreases ---------------------------------------------
    refreshed = client.get(f"{API}/products/{product_id}", headers=auth_headers).json()
    assert refreshed["stock"] == 12
    assert refreshed["stock_status"] == "low"

    # 4. Inventory transaction created -----------------------------------
    ledger = client.get(
        f"{API}/inventory/transactions",
        headers=auth_headers,
        params={"product_id": product_id, "transaction_type": "sale"},
    ).json()
    assert ledger["total"] == 1
    movement = ledger["items"][0]
    assert movement["quantity"] == -28
    assert movement["previous_stock"] == 40
    assert movement["new_stock"] == 12
    assert movement["reference"] == bill_no

    # 5. Low stock condition detected ------------------------------------
    assert sale_body["stock_updates"][0]["below_reorder_level"] is True
    assert any("reorder level" in message for message in sale_body["alerts_raised"])

    overview = client.get(f"{API}/inventory/overview", headers=auth_headers).json()
    assert overview["low_stock_count"] == 1

    # 6. Analytics updated -----------------------------------------------
    kpis = client.get(f"{API}/dashboard/kpis", headers=auth_headers).json()
    assert kpis["total_sales"] == 1
    # 28 x 500 = 14000 + 18% GST = 16520
    assert float(kpis["total_revenue"]) == 16520.0

    top_products = client.get(
        f"{API}/analytics/products", headers=auth_headers
    ).json()
    assert top_products[0]["name"] == "Wireless Mouse"
    assert top_products[0]["units_sold"] == 28
    # Gross profit: 28 x (500 - 300) = 5600
    assert float(top_products[0]["gross_profit"]) == 5600.0

    # 7. Forecast available ----------------------------------------------
    summary = client.get(
        f"{API}/forecasting/demand-summary", headers=auth_headers
    ).json()
    assert summary["items"]
    forecast_entry = next(
        item for item in summary["items"] if item["product_id"] == product_id
    )
    assert forecast_entry["forecast_demand"] > 0

    # 8. Reorder recommendation generated --------------------------------
    recommendation = client.get(
        f"{API}/inventory/recommendations/{product_id}",
        headers=auth_headers,
        params={"horizon_days": 7},
    ).json()
    assert recommendation["current_stock"] == 12
    assert recommendation["recommended_quantity"] > 0
    assert recommendation["urgency"] in {"critical", "high", "medium"}
    assert recommendation["reasons"]
    expected = max(
        0,
        round(
            recommendation["forecast_demand"]
            + recommendation["safety_stock"]
            - recommendation["current_stock"]
        ),
    )
    assert recommendation["recommended_quantity"] == expected

    # 9. Automation raises an alert ---------------------------------------
    scan = client.post(f"{API}/alerts/scan", headers=auth_headers).json()
    assert scan["total_open"] >= 1
    alerts = client.get(f"{API}/alerts", headers=auth_headers).json()["items"]
    stock_alert = next(a for a in alerts if a["entity_id"] == product_id)
    assert "Wireless Mouse" in stock_alert["title"]
    assert stock_alert["recommended_action"]

    # 10. AI explains the recommendation ----------------------------------
    ai = client.post(
        f"{API}/ai/chat",
        headers=auth_headers,
        json={"question": 'Why should I reorder "Wireless Mouse"?'},
    ).json()

    assert ai["routing"]["agent"] == "inventory_agent"
    assert ai["data_available"] is True
    answer = ai["answer"]
    assert "Wireless Mouse" in answer

    # The explanation must be built from the engine's own evidence.
    evidence = ai["data"]["recommendation"]["evidence"]
    assert evidence["current_stock"] == 12
    assert evidence["units_sold_last_30_days"] == 28
    assert "formula" in evidence
    assert str(recommendation["recommended_quantity"]) in answer


def test_stock_is_never_oversold_across_the_chain(
    client: TestClient, auth_headers: dict
) -> None:
    """Repeated sales must reconcile exactly with the inventory ledger."""
    product = client.post(
        f"{API}/products",
        headers=auth_headers,
        json={
            "name": "Ledger Test Item",
            "sku": "SKU-E2E-002",
            "category": "Grocery",
            "cost_price": "10.00",
            "selling_price": "25.00",
            "stock": 100,
            "reorder_level": 5,
        },
    ).json()
    product_id = product["id"]

    for quantity in (10, 15, 20, 5):
        response = client.post(
            f"{API}/sales",
            headers=auth_headers,
            json={"items": [{"product_id": product_id, "quantity": quantity}]},
        )
        assert response.status_code == 201

    # An oversized order must fail and change nothing.
    rejected = client.post(
        f"{API}/sales",
        headers=auth_headers,
        json={"items": [{"product_id": product_id, "quantity": 999}]},
    )
    assert rejected.status_code == 400

    final = client.get(f"{API}/products/{product_id}", headers=auth_headers).json()
    assert final["stock"] == 50

    ledger = client.get(
        f"{API}/inventory/transactions",
        headers=auth_headers,
        params={"product_id": product_id, "page_size": 50},
    ).json()
    # Opening stock plus four sales, and nothing for the rejected order.
    assert ledger["total"] == 5
    net_change = sum(row["quantity"] for row in ledger["items"])
    assert net_change == 50
    assert ledger["items"][0]["new_stock"] == 50


def test_void_restores_the_entire_chain(client: TestClient, auth_headers: dict) -> None:
    product = client.post(
        f"{API}/products",
        headers=auth_headers,
        json={
            "name": "Refund Item",
            "sku": "SKU-E2E-003",
            "category": "Grocery",
            "cost_price": "50.00",
            "selling_price": "80.00",
            "stock": 20,
            "reorder_level": 5,
        },
    ).json()

    sale = client.post(
        f"{API}/sales",
        headers=auth_headers,
        json={"items": [{"product_id": product["id"], "quantity": 12}]},
    ).json()

    assert client.get(f"{API}/dashboard/kpis", headers=auth_headers).json()["total_sales"] == 1

    client.delete(f"{API}/sales/{sale['sale']['id']}", headers=auth_headers)

    restored = client.get(f"{API}/products/{product['id']}", headers=auth_headers).json()
    assert restored["stock"] == 20

    kpis = client.get(f"{API}/dashboard/kpis", headers=auth_headers).json()
    assert kpis["total_sales"] == 0
    assert float(kpis["total_revenue"]) == 0.0
