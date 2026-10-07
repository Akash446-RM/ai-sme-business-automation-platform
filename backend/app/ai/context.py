"""Structured context construction and grounding rules.

The retrieval step of this RAG pipeline queries the business database and the
ML layer rather than a document index, because the questions an SME owner asks
are answered by live numbers, not by prose. The retrieved facts are assembled
into a strict, labelled context block; the language model may only rephrase
what appears there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

SYSTEM_PROMPT = """You are the business assistant inside an SME management platform.

Absolute rules:
1. Use ONLY the figures provided in the FACTS and DETAILS sections. They come
   from the business database and its forecasting models.
2. Never invent, estimate or round away a number that is not given to you.
3. If the context does not contain the answer, say clearly that the data is not
   available and suggest what the user could ask instead.
4. Quote concrete numbers when you make a claim.
5. When you explain a recommendation, use the reasons supplied in the context.
6. Be concise and practical. Write for a busy shop owner, not an analyst.
7. Amounts are in {currency}. Write them plainly, for example {symbol} 12,500.
"""


@dataclass
class BusinessContext:
    """Everything retrieved for one question."""

    intent: str
    agent: str
    summary: str = ""
    facts: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    period_label: Optional[str] = None
    has_data: bool = True
    suggestions: List[str] = field(default_factory=list)

    def add_fact(self, text: str) -> None:
        self.facts.append(f"- {text}")

    def add_detail(self, text: str) -> None:
        self.details.append(text)

    def add_source(self, source: str) -> None:
        if source not in self.sources:
            self.sources.append(source)

    def render_prompt(self, question: str) -> str:
        """Build the user prompt handed to the provider."""
        blocks: List[str] = [f"QUESTION:\n{question}\n"]
        if self.period_label:
            blocks.append(f"PERIOD:\n{self.period_label}\n")
        if self.summary:
            blocks.append(f"SUMMARY:\n{self.summary}\n")
        if self.facts:
            blocks.append("FACTS:\n" + "\n".join(self.facts) + "\n")
        if self.details:
            blocks.append("DETAILS:\n" + "\n\n".join(self.details) + "\n")
        if not self.has_data:
            blocks.append(
                "DATA AVAILABILITY:\nThe business database does not contain enough "
                "information to answer this question.\n"
            )
        return "\n".join(blocks)

    @staticmethod
    def system_prompt() -> str:
        return SYSTEM_PROMPT.format(
            currency=settings.currency, symbol=settings.currency_symbol
        )


def money(value: float | int) -> str:
    """Format a monetary amount for display inside the context."""
    return f"{settings.currency_symbol} {float(value):,.0f}"


def resolve_period(period: Optional[str], reference: date) -> Tuple[date, date, str]:
    """Translate a named period into concrete dates plus a readable label."""
    if period == "today":
        return reference, reference, f"today ({reference})"
    if period == "yesterday":
        day = reference - timedelta(days=1)
        return day, day, f"yesterday ({day})"
    if period == "this_week":
        start = reference - timedelta(days=reference.weekday())
        return start, reference, f"this week ({start} to {reference})"
    if period == "last_week":
        end = reference - timedelta(days=reference.weekday() + 1)
        start = end - timedelta(days=6)
        return start, end, f"last week ({start} to {end})"
    if period == "this_month":
        start = reference.replace(day=1)
        return start, reference, f"this month ({start} to {reference})"
    if period == "last_month":
        end = reference.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
        return start, end, f"last month ({start} to {end})"
    if period == "this_year":
        start = reference.replace(month=1, day=1)
        return start, reference, f"this year ({start} to {reference})"
    if period == "last_7_days":
        start = reference - timedelta(days=6)
        return start, reference, f"the last 7 days ({start} to {reference})"
    if period == "last_90_days":
        start = reference - timedelta(days=89)
        return start, reference, f"the last 90 days ({start} to {reference})"

    start = reference - timedelta(days=29)
    return start, reference, f"the last 30 days ({start} to {reference})"


NO_DATA_MESSAGE = (
    "I could not find enough information in the business data to answer that "
    "reliably. I can help with sales performance, revenue, product and category "
    "results, customer spending, stock levels, restocking recommendations and "
    "demand forecasts."
)
