"""Automation engine and alert endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest_helpers import API, create_product, create_sale

pytestmark = pytest.mark.api


def test_scan_detects_out_of_stock(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, name="Empty Item", stock=6, reorder_level=2)
    create_sale(client, auth_headers, product_id=product["id"], quantity=6)

    result = client.post(f"{API}/alerts/scan", headers=auth_headers).json()
    assert result["created"] >= 1
    assert result["by_type"].get("out_of_stock", 0) >= 1

    alerts = client.get(f"{API}/alerts", headers=auth_headers).json()["items"]
    entry = next(a for a in alerts if a["alert_type"] == "out_of_stock")
    assert entry["severity"] == "critical"
    assert "Empty Item" in entry["title"]
    assert entry["recommended_action"]
    assert entry["evidence"]["current_stock"] == 0


def test_scan_detects_low_stock(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, name="Low Item", stock=30, reorder_level=25)
    create_sale(client, auth_headers, product_id=product["id"], quantity=8)

    client.post(f"{API}/alerts/scan", headers=auth_headers)
    alerts = client.get(f"{API}/alerts", headers=auth_headers).json()["items"]
    types = {alert["alert_type"] for alert in alerts}
    assert types & {"low_stock", "stockout_risk"}


def test_scan_is_idempotent(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=5, reorder_level=20)
    create_sale(client, auth_headers, product_id=product["id"], quantity=3)

    first = client.post(f"{API}/alerts/scan", headers=auth_headers).json()
    second = client.post(f"{API}/alerts/scan", headers=auth_headers).json()

    assert first["created"] >= 1
    assert second["created"] == 0
    assert second["updated"] >= 1
    assert second["total_open"] == first["total_open"]


def test_resolved_condition_closes_alert(client: TestClient, auth_headers: dict) -> None:
    """Restocking a product must auto resolve its stock alert."""
    product = create_product(client, auth_headers, stock=4, reorder_level=20)
    create_sale(client, auth_headers, product_id=product["id"], quantity=2)

    first = client.post(f"{API}/alerts/scan", headers=auth_headers).json()
    assert first["total_open"] >= 1

    client.post(
        f"{API}/products/{product['id']}/adjust-stock",
        headers=auth_headers,
        json={"quantity": 500, "reason": "Bulk delivery received"},
    )
    second = client.post(f"{API}/alerts/scan", headers=auth_headers).json()
    assert second["auto_resolved"] >= 1
    assert second["total_open"] < first["total_open"]


def test_alert_summary_counts(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=3, reorder_level=15)
    create_sale(client, auth_headers, product_id=product["id"], quantity=3)
    client.post(f"{API}/alerts/scan", headers=auth_headers)

    summary = client.get(f"{API}/alerts/summary", headers=auth_headers).json()
    assert summary["total_open"] >= 1
    assert summary["critical"] >= 1
    assert summary["by_type"]


def test_update_alert_status(client: TestClient, auth_headers: dict) -> None:
    product = create_product(client, auth_headers, stock=2, reorder_level=10)
    create_sale(client, auth_headers, product_id=product["id"], quantity=2)
    client.post(f"{API}/alerts/scan", headers=auth_headers)

    alert = client.get(f"{API}/alerts", headers=auth_headers).json()["items"][0]
    response = client.patch(
        f"{API}/alerts/{alert['id']}",
        headers=auth_headers,
        json={"status": "acknowledged"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"


def test_scan_requires_manager_role(client: TestClient, auth_headers: dict) -> None:
    client.post(
        f"{API}/auth/register",
        json={"email": "junior@smedemo.com", "full_name": "Junior", "password": "Password123"},
    )
    token = client.post(
        f"{API}/auth/login",
        json={"email": "junior@smedemo.com", "password": "Password123"},
    ).json()["access_token"]

    assert (
        client.post(
            f"{API}/alerts/scan", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 403
    )


def test_ai_reports_alerts(client: TestClient, auth_headers: dict) -> None:
    """The business agent must read real alerts, not invent them."""
    product = create_product(client, auth_headers, name="Risky Item", stock=2, reorder_level=25)
    create_sale(client, auth_headers, product_id=product["id"], quantity=2)
    client.post(f"{API}/alerts/scan", headers=auth_headers)

    body = client.post(
        f"{API}/ai/chat",
        headers=auth_headers,
        json={"question": "What needs my attention right now?"},
    ).json()
    assert body["routing"]["intent"] == "alerts"
    assert body["data"]["summary"]["total_open"] >= 1
    assert "Risky Item" in body["answer"]


def test_alerts_require_authentication(client: TestClient) -> None:
    assert client.get(f"{API}/alerts").status_code == 401
