"""Forecasting endpoint tests.

These run without trained artifacts present, so they verify the platform
degrades gracefully rather than crashing when no model exists.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest_helpers import API, create_product, create_sale

pytestmark = pytest.mark.api


def test_status_reports_model_availability(client: TestClient, auth_headers: dict) -> None:
    body = client.get(f"{API}/forecasting/status", headers=auth_headers).json()
    assert "sales_model_trained" in body
    assert "demand_model_trained" in body
    assert "model_directory" in body


def test_forecast_requires_authentication(client: TestClient) -> None:
    assert client.get(f"{API}/forecasting/sales").status_code == 401


def test_untrained_model_returns_clear_error(
    client: TestClient, auth_headers: dict, monkeypatch
) -> None:
    from app.ml.registry import ModelRegistry

    monkeypatch.setattr(ModelRegistry, "sales_model", staticmethod(lambda: None))
    response = client.get(f"{API}/forecasting/sales", headers=auth_headers)
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "model_not_trained"
    assert "train_models" in body["error"]["message"]


def test_demand_summary_falls_back_to_statistics(
    client: TestClient, auth_headers: dict, monkeypatch
) -> None:
    """Without a trained model, recommendations still work using velocity."""
    from app.ml.registry import ModelRegistry

    monkeypatch.setattr(ModelRegistry, "demand_model", staticmethod(lambda: None))

    product = create_product(client, auth_headers, stock=5, reorder_level=20)
    create_sale(client, auth_headers, product_id=product["id"], quantity=3)

    body = client.get(
        f"{API}/forecasting/demand-summary", headers=auth_headers
    ).json()
    assert body["horizon_days"] == 7
    assert body["items"]
    assert body["items"][0]["forecast_source"] == "statistical_baseline"


def test_refresh_cache_requires_manager(client: TestClient, auth_headers: dict) -> None:
    client.post(
        f"{API}/auth/register",
        json={"email": "clerk@smedemo.com", "full_name": "Clerk", "password": "Password123"},
    )
    token = client.post(
        f"{API}/auth/login",
        json={"email": "clerk@smedemo.com", "password": "Password123"},
    ).json()["access_token"]

    assert (
        client.post(
            f"{API}/forecasting/refresh-cache",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 403
    )
    assert (
        client.post(f"{API}/forecasting/refresh-cache", headers=auth_headers).status_code
        == 200
    )
