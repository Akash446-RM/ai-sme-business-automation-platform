"""AI assistant orchestration.

Pipeline:

    question
      -> router            (rule based intent detection)
      -> agent             (business, inventory or analytics)
      -> services / ML     (real data retrieval)
      -> BusinessContext   (structured, labelled facts)
      -> provider          (LLM or offline renderer)
      -> grounded answer

The language model never queries the database and never sees anything the
agent did not retrieve, which is what keeps answers factual.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict

from sqlalchemy.orm import Session

from app.ai.agents import AnalyticsAgent, BusinessAgent, InventoryAgent
from app.ai.context import BusinessContext
from app.ai.providers import generate, provider_info
from app.ai.router import SUGGESTED_QUESTIONS, AgentName, Intent, route
from app.schemas.ai import AiStatus, ChatRequest, ChatResponse, RoutingInfo

logger = logging.getLogger(__name__)


class AIService:
    """Entry point for the conversational assistant."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._agents = {
            AgentName.ANALYTICS: AnalyticsAgent,
            AgentName.INVENTORY: InventoryAgent,
            AgentName.BUSINESS: BusinessAgent,
        }

    def ask(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        question = request.question.strip()

        routing = route(question)
        logger.info(
            "AI question routed: intent=%s agent=%s confidence=%.2f",
            routing.intent,
            routing.agent,
            routing.confidence,
        )

        agent = self._agents[routing.agent](self.db)
        try:
            context = agent.handle(routing, question)
        except Exception as exc:
            logger.exception("Agent %s failed", routing.agent)
            context = BusinessContext(
                intent=str(routing.intent),
                agent=str(routing.agent),
                has_data=False,
                summary=(
                    "I could not retrieve the business data needed to answer that. "
                    "Please try again, or ask a different question."
                ),
            )
            context.data = {"error": type(exc).__name__}

        response = generate(
            BusinessContext.system_prompt(), context.render_prompt(question)
        )

        suggestions = context.suggestions or self._related_questions(routing.intent)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return ChatResponse(
            answer=response.text,
            question=question,
            routing=RoutingInfo(
                intent=str(routing.intent),
                agent=str(routing.agent),
                confidence=routing.confidence,
                period=routing.period,
                horizon_days=routing.horizon_days,
                product_hint=routing.product_hint,
            ),
            sources=context.sources,
            data=context.data if request.include_data else None,
            grounded=True,
            data_available=context.has_data,
            provider=response.provider,
            model=response.model,
            fallback_used=response.fallback_used,
            suggestions=suggestions,
            generated_at=datetime.now(),
            elapsed_ms=elapsed_ms,
        )

    @staticmethod
    def _related_questions(intent: Intent) -> list[str]:
        """Offer sensible follow ups for the current topic."""
        follow_ups: Dict[Intent, list[str]] = {
            Intent.SALES_PERFORMANCE: [
                "What are my top selling products?",
                "Which category is performing best?",
                "What is the sales forecast for next week?",
            ],
            Intent.REVENUE: [
                "Which products generate the most revenue?",
                "How are sales performing this month?",
                "Who are my top customers?",
            ],
            Intent.TOP_PRODUCTS: [
                "Which products need restocking?",
                "Which products have declining demand?",
                "Which category is performing best?",
            ],
            Intent.REORDER: [
                "Which products are at risk of running out?",
                "What is the expected demand next week?",
                "What are my top selling products?",
            ],
            Intent.STOCK_STATUS: [
                "What should I reorder?",
                "Which products have not sold recently?",
                "Which products are at risk of running out?",
            ],
            Intent.DEMAND_FORECAST: [
                "What should I reorder?",
                "Which products have rising demand?",
                "How are sales performing this month?",
            ],
        }
        return follow_ups.get(intent, SUGGESTED_QUESTIONS[:3])

    @staticmethod
    def status() -> AiStatus:
        return AiStatus(
            provider=provider_info(),
            agents=["business_agent", "inventory_agent", "analytics_agent"],
            supported_intents=[
                str(intent) for intent in Intent if intent != Intent.UNKNOWN
            ],
            suggested_questions=SUGGESTED_QUESTIONS,
            grounding=(
                "Answers are built only from data retrieved from the business "
                "database and the trained forecasting models. The language model "
                "rephrases retrieved facts and is never the source of a number."
            ),
        )
