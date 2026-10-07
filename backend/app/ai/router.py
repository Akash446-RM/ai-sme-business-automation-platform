"""Intent detection and agent routing.

Routing is done with weighted keyword scoring rather than an LLM call. It is
deterministic, testable, free and instant, and the question space of a business
assistant is narrow enough that scoring works reliably. The LLM is reserved for
what it is genuinely good at: turning retrieved facts into prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class _ValueEnum(str, Enum):
    """String enum whose str() is the plain value, not 'Class.MEMBER'."""

    def __str__(self) -> str:
        return str(self.value)


class Intent(_ValueEnum):
    """Question categories the assistant understands."""

    SALES_PERFORMANCE = "sales_performance"
    REVENUE = "revenue"
    TOP_PRODUCTS = "top_products"
    WORST_PRODUCTS = "worst_products"
    CATEGORY_PERFORMANCE = "category_performance"
    TOP_CUSTOMERS = "top_customers"
    EMPLOYEE_PERFORMANCE = "employee_performance"
    STOCK_STATUS = "stock_status"
    REORDER = "reorder"
    STOCKOUT_RISK = "stockout_risk"
    DEMAND_FORECAST = "demand_forecast"
    SALES_FORECAST = "sales_forecast"
    DEMAND_TREND = "demand_trend"
    PRODUCT_EXPLANATION = "product_explanation"
    DEAD_STOCK = "dead_stock"
    BUSINESS_OVERVIEW = "business_overview"
    ALERTS = "alerts"
    UNKNOWN = "unknown"


class AgentName(_ValueEnum):
    ANALYTICS = "analytics_agent"
    INVENTORY = "inventory_agent"
    BUSINESS = "business_agent"


# Intent -> the agent that can answer it
INTENT_AGENTS: Dict[Intent, AgentName] = {
    Intent.SALES_PERFORMANCE: AgentName.ANALYTICS,
    Intent.REVENUE: AgentName.ANALYTICS,
    Intent.TOP_PRODUCTS: AgentName.ANALYTICS,
    Intent.WORST_PRODUCTS: AgentName.ANALYTICS,
    Intent.CATEGORY_PERFORMANCE: AgentName.ANALYTICS,
    Intent.TOP_CUSTOMERS: AgentName.ANALYTICS,
    Intent.EMPLOYEE_PERFORMANCE: AgentName.ANALYTICS,
    Intent.SALES_FORECAST: AgentName.ANALYTICS,
    Intent.DEMAND_TREND: AgentName.ANALYTICS,
    Intent.STOCK_STATUS: AgentName.INVENTORY,
    Intent.REORDER: AgentName.INVENTORY,
    Intent.STOCKOUT_RISK: AgentName.INVENTORY,
    Intent.DEMAND_FORECAST: AgentName.INVENTORY,
    Intent.PRODUCT_EXPLANATION: AgentName.INVENTORY,
    Intent.DEAD_STOCK: AgentName.INVENTORY,
    Intent.BUSINESS_OVERVIEW: AgentName.BUSINESS,
    Intent.ALERTS: AgentName.BUSINESS,
    Intent.UNKNOWN: AgentName.BUSINESS,
}


@dataclass
class IntentPattern:
    """Weighted signals that point at one intent."""

    intent: Intent
    strong: Tuple[str, ...] = ()      # phrases that almost decide the intent
    weak: Tuple[str, ...] = ()        # supporting words
    required: Tuple[str, ...] = ()    # at least one of these must appear


PATTERNS: List[IntentPattern] = [
    IntentPattern(
        Intent.REORDER,
        strong=("what should i reorder", "need restocking", "need to restock",
                "what to reorder", "should i reorder", "reorder recommendation",
                "which products need", "what do i need to order", "purchase order"),
        weak=("reorder", "restock", "order more", "replenish", "buy more"),
    ),
    IntentPattern(
        Intent.STOCKOUT_RISK,
        strong=("run out of stock", "stockout", "stock out", "will i run out",
                "risk of running out", "about to run out"),
        weak=("shortage", "run out", "insufficient stock"),
    ),
    IntentPattern(
        Intent.STOCK_STATUS,
        strong=("low stock", "out of stock", "stock level", "current stock",
                "inventory status", "how much stock", "what is in stock"),
        weak=("stock", "inventory", "on hand", "available"),
    ),
    IntentPattern(
        Intent.DEAD_STOCK,
        strong=("dead stock", "not selling", "slow moving", "never sold",
                "stuck inventory", "obsolete stock"),
        weak=("slow", "stagnant", "unsold"),
    ),
    IntentPattern(
        Intent.PRODUCT_EXPLANATION,
        strong=("why should i reorder", "why do i need to reorder", "explain why",
                "why is this recommended", "reason for reorder", "justify"),
        weak=("why",),
    ),
    IntentPattern(
        Intent.DEMAND_FORECAST,
        strong=("expected demand", "demand next week", "forecast demand",
                "how many will i sell", "predicted demand", "demand forecast",
                "how much will sell"),
        weak=("demand", "forecast", "predict", "expected"),
    ),
    IntentPattern(
        Intent.SALES_FORECAST,
        strong=("sales forecast", "revenue forecast", "forecast sales",
                "predict revenue", "expected revenue", "next week sales",
                "how much will i sell next"),
        weak=("forecast", "projection", "outlook"),
    ),
    IntentPattern(
        Intent.DEMAND_TREND,
        strong=("declining demand", "falling demand", "rising demand",
                "increasing demand", "demand trend", "growing demand",
                "products are declining", "losing popularity"),
        weak=("trend", "declining", "rising", "increasing", "falling"),
    ),
    IntentPattern(
        Intent.TOP_PRODUCTS,
        strong=("top selling", "best selling", "top products", "best products",
                "highest selling", "top performers", "most popular"),
        weak=("best", "top", "popular", "selling"),
        required=("product", "item", "sku", "sell", "seller"),
    ),
    IntentPattern(
        Intent.WORST_PRODUCTS,
        strong=("worst performing", "worst products", "lowest selling",
                "poorly performing", "bottom products", "least selling"),
        weak=("worst", "poor", "lowest", "bottom"),
        required=("product", "item", "sku", "perform", "sell"),
    ),
    IntentPattern(
        Intent.CATEGORY_PERFORMANCE,
        strong=("which category", "category performance", "best category",
                "category is performing", "categories performing", "by category"),
        weak=("category", "categories", "segment"),
    ),
    IntentPattern(
        Intent.TOP_CUSTOMERS,
        strong=("top customers", "best customers", "biggest customers",
                "who are my customers", "highest spending", "loyal customers"),
        weak=("customer", "customers", "buyer", "client"),
    ),
    IntentPattern(
        Intent.EMPLOYEE_PERFORMANCE,
        strong=("best employee", "top employee", "employee performance",
                "staff performance", "who sold the most", "sales team"),
        weak=("employee", "staff", "cashier", "salesperson"),
    ),
    IntentPattern(
        Intent.REVENUE,
        strong=("how much revenue", "total revenue", "revenue this month",
                "revenue generated", "how much did we make", "how much money",
                "why did revenue", "revenue decrease", "revenue increase",
                "profit", "margin"),
        weak=("revenue", "income", "earnings", "turnover", "profit"),
    ),
    IntentPattern(
        Intent.SALES_PERFORMANCE,
        strong=("how are sales", "sales performance", "sales this month",
                "sales this week", "sales today", "my sales", "were my sales",
                "how did we do", "sales doing", "sales going"),
        weak=("sales", "sold", "selling", "performance"),
    ),
    IntentPattern(
        Intent.ALERTS,
        strong=("what alerts", "any alerts", "warnings", "what needs attention",
                "any problems", "issues", "what should i worry"),
        weak=("alert", "warning", "attention", "urgent"),
    ),
    IntentPattern(
        Intent.BUSINESS_OVERVIEW,
        strong=("business overview", "how is my business", "business summary",
                "overall performance", "how is the business", "summarise",
                "summarize", "give me an overview", "how are we doing"),
        weak=("business", "overview", "summary", "overall"),
    ),
]

STRONG_WEIGHT = 10.0
WEAK_WEIGHT = 2.0
REQUIRED_PENALTY = 0.35

# Time expressions the agents translate into concrete date ranges.
PERIOD_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "today": ("today", "so far today"),
    "yesterday": ("yesterday",),
    "this_week": ("this week", "current week"),
    "last_week": ("last week", "previous week"),
    "this_month": ("this month", "current month", "month to date"),
    "last_month": ("last month", "previous month"),
    "this_year": ("this year", "year to date", "current year"),
    "last_7_days": ("last 7 days", "past 7 days", "last seven days", "past week"),
    "last_30_days": ("last 30 days", "past 30 days", "last thirty days", "past month"),
    "last_90_days": ("last 90 days", "past 90 days", "last quarter", "past quarter"),
}

HORIZON_PATTERN = re.compile(
    r"next\s+(\d+)\s*(day|days|week|weeks|month|months)|next\s+(week|month)", re.IGNORECASE
)


@dataclass
class RoutingResult:
    """What the router decided, and why."""

    intent: Intent
    agent: AgentName
    confidence: float
    period: Optional[str] = None
    horizon_days: Optional[int] = None
    product_hint: Optional[str] = None
    scores: Dict[str, float] = field(default_factory=dict)


def _normalise(question: str) -> str:
    text = question.lower().strip()
    text = re.sub(r"[^\w\s%]", " ", text)
    return re.sub(r"\s+", " ", text)


def detect_period(question: str) -> Optional[str]:
    """Map a natural time expression onto a named period."""
    text = _normalise(question)
    for period, phrases in PERIOD_PATTERNS.items():
        if any(phrase in text for phrase in phrases):
            return period
    return None


def detect_horizon_days(question: str) -> Optional[int]:
    """Extract a forecast horizon such as 'next 14 days' or 'next month'."""
    match = HORIZON_PATTERN.search(question)
    if not match:
        return None
    if match.group(3):
        return 7 if match.group(3).lower() == "week" else 30
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("week"):
        return amount * 7
    if unit.startswith("month"):
        return amount * 30
    return amount


def extract_product_hint(question: str) -> Optional[str]:
    """Pull a probable product name out of the question.

    Quoted text wins; otherwise the words following 'for', 'of' or 'about'
    are treated as a candidate that the agent resolves against the catalogue.
    """
    quoted = re.search(r"[\"']([^\"']{3,60})[\"']", question)
    if quoted:
        return quoted.group(1).strip()

    match = re.search(
        r"\b(?:for|of|about|on)\s+([A-Za-z0-9][\w\s\-\.]{2,50}?)"
        r"(?:\s*[\?\.,]|\s+(?:in|over|during|next|last|this)\b|$)",
        question,
        flags=re.IGNORECASE,
    )
    if match:
        candidate = match.group(1).strip()
        stopwords = {
            "me", "us", "my", "our", "the", "this", "that", "it", "them",
            "sales", "revenue", "stock", "inventory", "business", "today",
            "yesterday", "products", "customers",
        }
        if candidate.lower() not in stopwords and len(candidate) >= 3:
            return candidate
    return None


def route(question: str) -> RoutingResult:
    """Score every intent and select the winner."""
    text = _normalise(question)
    scores: Dict[Intent, float] = {}

    for pattern in PATTERNS:
        score = 0.0
        for phrase in pattern.strong:
            if phrase in text:
                score += STRONG_WEIGHT
        for word in pattern.weak:
            if re.search(rf"\b{re.escape(word)}\b", text):
                score += WEAK_WEIGHT
        if score and pattern.required:
            if not any(
                re.search(rf"\b{re.escape(word)}", text) for word in pattern.required
            ):
                score *= REQUIRED_PENALTY
        if score:
            scores[pattern.intent] = scores.get(pattern.intent, 0.0) + score

    if not scores:
        return RoutingResult(
            intent=Intent.UNKNOWN,
            agent=AgentName.BUSINESS,
            confidence=0.0,
            scores={},
        )

    intent = max(scores, key=lambda key: scores[key])
    top_score = scores[intent]
    total = sum(scores.values())
    confidence = round(top_score / total, 3) if total else 0.0

    return RoutingResult(
        intent=intent,
        agent=INTENT_AGENTS[intent],
        confidence=confidence,
        period=detect_period(question),
        horizon_days=detect_horizon_days(question),
        product_hint=extract_product_hint(question),
        scores={str(key): round(value, 2) for key, value in scores.items()},
    )


SUGGESTED_QUESTIONS: List[str] = [
    "How are sales performing this month?",
    "What are my top selling products?",
    "Which products need restocking?",
    "What should I reorder?",
    "Which products have declining demand?",
    "Which category is performing best?",
    "What is the expected demand next week?",
    "Who are my top customers?",
    "How much revenue did we generate this month?",
    "What needs my attention right now?",
]
