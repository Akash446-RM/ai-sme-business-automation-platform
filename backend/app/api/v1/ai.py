"""AI business assistant endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter

from app.ai.router import SUGGESTED_QUESTIONS, route
from app.ai.service import AIService
from app.core.deps import CurrentUser, DbSession
from app.schemas.ai import AiStatus, ChatRequest, ChatResponse

router = APIRouter(prefix="/ai", tags=["ai assistant"])


@router.post("/chat", response_model=ChatResponse, summary="Ask the business assistant")
def chat(payload: ChatRequest, db: DbSession, _: CurrentUser) -> ChatResponse:
    return AIService(db).ask(payload)


@router.get("/status", response_model=AiStatus, summary="AI configuration and capabilities")
def status(_: CurrentUser) -> AiStatus:
    return AIService.status()


@router.get(
    "/suggestions",
    response_model=List[str],
    summary="Suggested questions for the chat interface",
)
def suggestions(_: CurrentUser) -> List[str]:
    return SUGGESTED_QUESTIONS


@router.post("/explain-routing", summary="Show how a question would be classified")
def explain_routing(payload: ChatRequest, _: CurrentUser) -> dict:
    """Transparency helper: exposes the router's scoring for a question."""
    result = route(payload.question)
    return {
        "question": payload.question,
        "intent": str(result.intent),
        "agent": str(result.agent),
        "confidence": result.confidence,
        "detected_period": result.period,
        "detected_horizon_days": result.horizon_days,
        "detected_product": result.product_hint,
        "intent_scores": result.scores,
    }
