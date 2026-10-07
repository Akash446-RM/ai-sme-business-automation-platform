"""Helpers shared by the API and integration test modules."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi.testclient import TestClient

API = "/api/v1"


def create_product(
    client: TestClient,
    headers: dict,
    *,
    name: str = "Wireless Mouse",
    sku: str = "SKU-MOUSE-001",
    category: str = "Electronics",
    cost_price: str = "300.00",
    selling_price: str = "499.00",
    stock: int = 50,
    reorder_level: int = 10,
    **overrides: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": name,
        "sku": sku,
        "category": category,
        "cost_price": cost_price,
        "selling_price": selling_price,
        "stock": stock,
        "reorder_level": reorder_level,
    }
    payload.update(overrides)
    response = client.post(f"{API}/products", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_customer(
    client: TestClient, headers: dict, *, name: str = "Acme Retail", **overrides: Any
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name, "city": "Bengaluru"}
    payload.update(overrides)
    response = client.post(f"{API}/customers", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_employee(
    client: TestClient, headers: dict, *, name: str = "Ravi Kumar", **overrides: Any
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name, "role": "Sales Executive"}
    payload.update(overrides)
    response = client.post(f"{API}/employees", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_sale(
    client: TestClient,
    headers: dict,
    *,
    product_id: int,
    quantity: int = 2,
    customer_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    **overrides: Any,
):
    payload: Dict[str, Any] = {
        "items": [{"product_id": product_id, "quantity": quantity}],
        "payment_method": "cash",
    }
    if customer_id:
        payload["customer_id"] = customer_id
    if employee_id:
        payload["employee_id"] = employee_id
    payload.update(overrides)
    return client.post(f"{API}/sales", headers=headers, json=payload)
