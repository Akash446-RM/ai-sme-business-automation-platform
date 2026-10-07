"""Analytics, dashboard and report endpoint tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest_helpers import API, create_customer, create_employee, create_product

pytestmark = pytest.mark.api


def _sale_on(
    client: TestClient,
    headers: dict,
    product_id: int,
    quantity: int,
    when: datetime,
    **extra,
):
    payload = {
        "items": [{"product_id": product_id, "quantity": quantity}],
        "sale_date": when.isoformat(),
        "gst_rate": "0.00",
    }
    payload.update(extra)
    response = client.post(f"{API}/sales", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def seeded(client: TestClient, auth_headers: dict) -> dict:
    """A tiny but fully controlled dataset with known totals."""
    product_a = create_product(
        client,
        auth_headers,
        name="Product A",
        sku="SKU-A",
        category="Electronics",
        cost_price="60.00",
        selling_price="100.00",
        stock=1000,
    )
    product_b = create_product(
        client,
        auth_headers,
        name="Product B",
        sku="SKU-B",
        category="Grocery",
        cost_price="10.00",
        selling_price="20.00",
        stock=1000,
    )
    customer = create_customer(client, auth_headers)
    employee = create_employee(client, auth_headers)

    today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    # Current window: 10 x A (1000) + 20 x B (400) = 1400 revenue
    _sale_on(client, auth_headers, product_a["id"], 10, today - timedelta(days=1),
             customer_id=customer["id"], employee_id=employee["id"])
    _sale_on(client, auth_headers, product_b["id"], 20, today - timedelta(days=2),
             customer_id=customer["id"], employee_id=employee["id"])
    # Older sale, outside a 7 day window: 5 x A = 500
    _sale_on(client, auth_headers, product_a["id"], 5, today - timedelta(days=40))

    return {
        "product_a": product_a,
        "product_b": product_b,
        "customer": customer,
        "employee": employee,
        "today": today,
    }


def test_summary_totals_are_accurate(client: TestClient, auth_headers: dict, seeded) -> None:
    date_to = seeded["today"].date()
    date_from = date_to - timedelta(days=6)
    body = client.get(
        f"{API}/analytics/summary",
        headers=auth_headers,
        params={"date_from": str(date_from), "date_to": str(date_to)},
    ).json()

    assert float(body["revenue"]) == 1400.0
    assert body["transactions"] == 2
    assert body["units_sold"] == 30
    assert float(body["average_order_value"]) == 700.0


def test_sales_trend_groups_by_day(client: TestClient, auth_headers: dict, seeded) -> None:
    date_to = seeded["today"].date()
    body = client.get(
        f"{API}/analytics/sales-trend",
        headers=auth_headers,
        params={"date_from": str(date_to - timedelta(days=6)), "date_to": str(date_to)},
    ).json()

    assert body["granularity"] == "day"
    assert len(body["points"]) == 2
    assert float(body["total_revenue"]) == 1400.0
    assert body["total_transactions"] == 2


def test_product_performance_ranking(client: TestClient, auth_headers: dict, seeded) -> None:
    date_to = seeded["today"].date()
    body = client.get(
        f"{API}/analytics/products",
        headers=auth_headers,
        params={"date_from": str(date_to - timedelta(days=6)), "date_to": str(date_to)},
    ).json()

    assert body[0]["name"] == "Product A"
    assert float(body[0]["revenue"]) == 1000.0
    assert body[0]["units_sold"] == 10
    # Gross profit: 10 units x (100 - 60) = 400
    assert float(body[0]["gross_profit"]) == 400.0
    assert body[0]["revenue_share_percent"] == pytest.approx(71.43, abs=0.1)


def test_worst_performers_order_ascending(
    client: TestClient, auth_headers: dict, seeded
) -> None:
    date_to = seeded["today"].date()
    body = client.get(
        f"{API}/analytics/products",
        headers=auth_headers,
        params={
            "date_from": str(date_to - timedelta(days=6)),
            "date_to": str(date_to),
            "order": "bottom",
        },
    ).json()
    assert body[0]["name"] == "Product B"


def test_category_performance(client: TestClient, auth_headers: dict, seeded) -> None:
    date_to = seeded["today"].date()
    body = client.get(
        f"{API}/analytics/categories",
        headers=auth_headers,
        params={"date_from": str(date_to - timedelta(days=6)), "date_to": str(date_to)},
    ).json()

    electronics = next(row for row in body if row["category"] == "Electronics")
    assert float(electronics["revenue"]) == 1000.0
    assert electronics["revenue_share_percent"] == pytest.approx(71.43, abs=0.1)
    assert sum(row["revenue_share_percent"] for row in body) == pytest.approx(100.0, abs=0.1)


def test_top_customers(client: TestClient, auth_headers: dict, seeded) -> None:
    body = client.get(f"{API}/analytics/customers", headers=auth_headers).json()
    assert body[0]["name"] == "Acme Retail"
    assert body[0]["total_orders"] == 2
    assert float(body[0]["total_spent"]) == 1400.0


def test_employee_leaderboard(client: TestClient, auth_headers: dict, seeded) -> None:
    body = client.get(f"{API}/analytics/employees", headers=auth_headers).json()
    assert body[0]["name"] == "Ravi Kumar"
    assert body[0]["transactions"] == 2


def test_payment_mix_shares_sum_to_100(
    client: TestClient, auth_headers: dict, seeded
) -> None:
    body = client.get(f"{API}/analytics/payment-mix", headers=auth_headers).json()
    assert sum(row["share_percent"] for row in body) == pytest.approx(100.0, abs=0.1)


def test_weekday_pattern_has_valid_days(
    client: TestClient, auth_headers: dict, seeded
) -> None:
    body = client.get(f"{API}/analytics/weekday-pattern", headers=auth_headers).json()
    assert body
    valid = {
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    }
    assert all(row["weekday"] in valid for row in body)
    assert sum(row["transactions"] for row in body) == 3


def test_dashboard_kpis_reflect_database(
    client: TestClient, auth_headers: dict, seeded
) -> None:
    body = client.get(f"{API}/dashboard/kpis", headers=auth_headers).json()
    assert body["total_products"] == 2
    assert body["total_customers"] == 1
    assert body["total_employees"] == 1
    assert body["total_sales"] == 3
    assert float(body["total_revenue"]) == 1900.0
    assert float(body["average_order_value"]) == pytest.approx(633.33, abs=0.01)


def test_dashboard_summary_structure(
    client: TestClient, auth_headers: dict, seeded
) -> None:
    body = client.get(f"{API}/dashboard/summary", headers=auth_headers).json()
    assert "kpis" in body
    assert isinstance(body["revenue_trend"], list)
    assert isinstance(body["top_products"], list)
    assert isinstance(body["insights"], list)
    assert len(body["recent_sales"]) == 3


def test_dashboard_insights_are_data_driven(
    client: TestClient, auth_headers: dict
) -> None:
    """An out of stock product must surface as a critical insight."""
    create_product(client, auth_headers, sku="SKU-EMPTY", stock=0, reorder_level=5)
    body = client.get(f"{API}/dashboard/insights", headers=auth_headers).json()
    types = {insight["type"] for insight in body}
    assert "out_of_stock" in types
    entry = next(item for item in body if item["type"] == "out_of_stock")
    assert entry["severity"] == "critical"
    assert "1" in entry["title"]


def test_sales_report(client: TestClient, auth_headers: dict, seeded) -> None:
    date_to = seeded["today"].date()
    body = client.get(
        f"{API}/reports/sales",
        headers=auth_headers,
        params={"date_from": str(date_to - timedelta(days=6)), "date_to": str(date_to)},
    ).json()

    assert body["meta"]["report_type"] == "sales"
    assert float(body["total_revenue"]) == 1400.0
    # Gross profit: A 10x40=400, B 20x10=200 -> 600
    assert float(body["gross_profit"]) == 600.0
    assert body["gross_margin_percent"] == pytest.approx(42.86, abs=0.1)


def test_inventory_report(client: TestClient, auth_headers: dict, seeded) -> None:
    body = client.get(f"{API}/reports/inventory", headers=auth_headers).json()
    assert body["meta"]["report_type"] == "inventory"
    assert body["total_products"] == 2
    assert isinstance(body["reorder_recommendations"], list)
    assert isinstance(body["valuation_by_category"], list)


def test_business_summary_report(client: TestClient, auth_headers: dict, seeded) -> None:
    date_to = seeded["today"].date()
    body = client.get(
        f"{API}/reports/business-summary",
        headers=auth_headers,
        params={"date_from": str(date_to - timedelta(days=6)), "date_to": str(date_to)},
    ).json()

    assert float(body["revenue"]) == 1400.0
    assert body["transactions"] == 2
    assert body["active_customers"] == 1
    assert body["headline_findings"], "summary must include narrative findings"
    assert any("Product A" in finding for finding in body["headline_findings"])


def test_customer_report_repeat_rate(client: TestClient, auth_headers: dict, seeded) -> None:
    body = client.get(f"{API}/reports/customers", headers=auth_headers).json()
    assert body["total_active_customers"] == 1
    assert body["repeat_customer_count"] == 1
    assert body["repeat_rate_percent"] == 100.0


def test_analytics_requires_authentication(client: TestClient) -> None:
    assert client.get(f"{API}/analytics/revenue").status_code == 401
    assert client.get(f"{API}/dashboard/kpis").status_code == 401
    assert client.get(f"{API}/reports/sales").status_code == 401
