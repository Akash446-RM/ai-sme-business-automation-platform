"""AI assistant endpoint tests, focused on grounding."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest_helpers import API, create_customer, create_product, create_sale

pytestmark = pytest.mark.api


@pytest.fixture()
def business(client: TestClient, auth_headers: dict) -> dict:
    product = create_product(
        client,
        auth_headers,
        name="Wireless Mouse",
        sku="SKU-WM-1",
        category="Electronics",
        cost_price="300.00",
        selling_price="500.00",
        stock=12,
        reorder_level=20,
    )
    customer = create_customer(client, auth_headers, name="Acme Retail")
    create_sale(
        client,
        auth_headers,
        product_id=product["id"],
        quantity=8,
        customer_id=customer["id"],
    )
    return {"product": product, "customer": customer}


def ask(client: TestClient, headers: dict, question: str, include_data: bool = True):
    response = client.post(
        f"{API}/ai/chat",
        headers=headers,
        json={"question": question, "include_data": include_data},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_requires_authentication(client: TestClient) -> None:
    assert client.post(f"{API}/ai/chat", json={"question": "hello there"}).status_code == 401


def test_status_reports_provider_and_agents(client: TestClient, auth_headers: dict) -> None:
    body = client.get(f"{API}/ai/status", headers=auth_headers).json()
    assert body["provider"]["active"] in {"offline", "openai_compat", "gemini", "ollama"}
    assert set(body["agents"]) == {"business_agent", "inventory_agent", "analytics_agent"}
    assert body["suggested_questions"]
    assert "never the source of a number" in body["grounding"]


def test_sales_answer_quotes_real_figures(
    client: TestClient, auth_headers: dict, business
) -> None:
    body = ask(client, auth_headers, "How are sales performing this month?")
    assert body["routing"]["intent"] == "sales_performance"
    assert body["routing"]["agent"] == "analytics_agent"
    assert body["data_available"] is True
    # 8 units x 500 = 4000 + 18% GST = 4720
    assert "4,720" in body["answer"] or "4720" in body["answer"]
    assert body["sources"]


def test_top_products_answer_names_the_product(
    client: TestClient, auth_headers: dict, business
) -> None:
    body = ask(client, auth_headers, "What are my top selling products?")
    assert body["routing"]["intent"] == "top_products"
    assert "Wireless Mouse" in body["answer"]
    assert body["data"]["products"][0]["units_sold"] == 8


def test_reorder_answer_is_explainable(
    client: TestClient, auth_headers: dict, business
) -> None:
    body = ask(client, auth_headers, "What should I reorder?")
    assert body["routing"]["intent"] == "reorder"
    assert body["routing"]["agent"] == "inventory_agent"
    assert "Wireless Mouse" in body["answer"]
    recommendations = body["data"]["recommendations"]
    assert recommendations
    assert recommendations[0]["reasons"], "recommendation must carry its reasons"


def test_explanation_answer_uses_engine_reasons(
    client: TestClient, auth_headers: dict, business
) -> None:
    body = ask(client, auth_headers, 'Why should I reorder "Wireless Mouse"?')
    assert body["routing"]["product_hint"] == "Wireless Mouse"
    answer = body["answer"].lower()
    assert "wireless mouse" in answer
    assert "formula" in body["answer"] or "recommended" in answer
    evidence = body["data"]["recommendation"]["evidence"]
    assert evidence["current_stock"] == 4  # 12 opening - 8 sold


def test_stock_question_reports_real_counts(
    client: TestClient, auth_headers: dict, business
) -> None:
    body = ask(client, auth_headers, "What is my current stock situation?")
    assert body["routing"]["agent"] == "inventory_agent"
    assert body["data"]["overview"]["total_products"] == 1


def test_customer_question(client: TestClient, auth_headers: dict, business) -> None:
    body = ask(client, auth_headers, "Who are my top customers?")
    assert body["routing"]["intent"] == "top_customers"
    assert "Acme Retail" in body["answer"]


def test_unknown_question_refuses_to_guess(client: TestClient, auth_headers: dict) -> None:
    body = ask(client, auth_headers, "What is the capital of France?")
    assert body["routing"]["intent"] == "unknown"
    assert body["data_available"] is False
    assert "Paris" not in body["answer"]
    assert "could not find enough information" in body["answer"].lower()
    assert body["suggestions"]


def test_answer_on_empty_database_admits_no_data(
    client: TestClient, auth_headers: dict
) -> None:
    """With no sales at all the assistant must not invent numbers."""
    body = ask(client, auth_headers, "How are sales performing this month?")
    assert body["data_available"] is False
    assert "no recorded sales" in body["answer"].lower()


def test_response_includes_provenance(client: TestClient, auth_headers: dict, business) -> None:
    body = ask(client, auth_headers, "How much revenue did we generate this month?")
    assert body["grounded"] is True
    assert body["provider"]
    assert body["sources"]
    assert body["elapsed_ms"] >= 0


def test_routing_explanation_endpoint(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        f"{API}/ai/explain-routing",
        headers=auth_headers,
        json={"question": "What should I reorder next week?"},
    )
    body = response.json()
    assert body["intent"] == "reorder"
    assert body["detected_horizon_days"] == 7
    assert body["intent_scores"]


def test_suggestions_endpoint(client: TestClient, auth_headers: dict) -> None:
    body = client.get(f"{API}/ai/suggestions", headers=auth_headers).json()
    assert len(body) >= 5
    assert any("reorder" in question.lower() for question in body)
