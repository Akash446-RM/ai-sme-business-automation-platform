"""Intent routing tests."""

from __future__ import annotations

import pytest

from app.ai.router import (
    AgentName,
    Intent,
    detect_horizon_days,
    detect_period,
    extract_product_hint,
    route,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What were my sales this month?", Intent.SALES_PERFORMANCE),
        ("How are sales performing?", Intent.SALES_PERFORMANCE),
        ("How much revenue did we generate this month?", Intent.REVENUE),
        ("Why did revenue decrease?", Intent.REVENUE),
        ("What are my top-selling products?", Intent.TOP_PRODUCTS),
        ("Show me the best selling products", Intent.TOP_PRODUCTS),
        ("Which products are worst performing?", Intent.WORST_PRODUCTS),
        ("Which category is performing best?", Intent.CATEGORY_PERFORMANCE),
        ("Who are my top customers?", Intent.TOP_CUSTOMERS),
        ("Which products need restocking?", Intent.REORDER),
        ("What should I reorder?", Intent.REORDER),
        ("Which products have declining demand?", Intent.DEMAND_TREND),
        ("What is expected demand next week?", Intent.DEMAND_FORECAST),
        ("Which products have dead stock?", Intent.DEAD_STOCK),
        ("How is my business doing?", Intent.BUSINESS_OVERVIEW),
        ("What needs attention?", Intent.ALERTS),
    ],
)
def test_questions_route_to_expected_intent(question: str, expected: Intent) -> None:
    result = route(question)
    assert result.intent == expected, f"{question!r} -> {result.intent} (scores {result.scores})"


def test_unrelated_question_is_unknown() -> None:
    result = route("What is the capital of France?")
    assert result.intent == Intent.UNKNOWN
    assert result.agent == AgentName.BUSINESS
    assert result.confidence == 0.0


def test_inventory_questions_use_inventory_agent() -> None:
    for question in ("What should I reorder?", "Which items are low on stock?"):
        assert route(question).agent == AgentName.INVENTORY


def test_analytics_questions_use_analytics_agent() -> None:
    for question in ("What are my top products?", "Who are my best customers?"):
        assert route(question).agent == AgentName.ANALYTICS


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What were my sales today?", "today"),
        ("Sales yesterday please", "yesterday"),
        ("Revenue this month", "this_month"),
        ("How did we do last month?", "last_month"),
        ("Sales this year", "this_year"),
        ("Revenue over the last 7 days", "last_7_days"),
        ("Show the last 90 days", "last_90_days"),
    ],
)
def test_period_detection(question: str, expected: str) -> None:
    assert detect_period(question) == expected


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What is demand next week?", 7),
        ("Forecast the next 14 days", 14),
        ("Demand for the next 2 weeks", 14),
        ("Sales next month", 30),
        ("What are my top products?", None),
    ],
)
def test_horizon_detection(question: str, expected) -> None:
    assert detect_horizon_days(question) == expected


def test_product_hint_from_quotes() -> None:
    assert extract_product_hint('Why should I reorder "Wireless Mouse"?') == "Wireless Mouse"


def test_product_hint_from_preposition() -> None:
    hint = extract_product_hint("What is the forecast for Bluetooth Keyboard next week?")
    assert hint == "Bluetooth Keyboard"


def test_product_hint_ignores_generic_words() -> None:
    assert extract_product_hint("Show me the sales") is None


def test_confidence_is_bounded() -> None:
    result = route("What should I reorder?")
    assert 0.0 < result.confidence <= 1.0
