"""AI assistant schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """A question for the business assistant."""

    question: str = Field(min_length=2, max_length=500)
    include_data: bool = Field(
        default=True, description="Return the structured data behind the answer"
    )


class RoutingInfo(BaseModel):
    """How the question was classified, exposed for transparency."""

    intent: str
    agent: str
    confidence: float
    period: Optional[str] = None
    horizon_days: Optional[int] = None
    product_hint: Optional[str] = None


class ChatResponse(BaseModel):
    """A grounded answer plus its provenance."""

    answer: str
    question: str
    routing: RoutingInfo
    sources: List[str] = Field(
        default_factory=list, description="Where the facts in this answer came from"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured data the answer is based on"
    )
    grounded: bool = True
    data_available: bool = True
    provider: str
    model: Optional[str] = None
    fallback_used: bool = False
    suggestions: List[str] = Field(default_factory=list)
    generated_at: datetime
    elapsed_ms: int


class AiStatus(BaseModel):
    """Configuration and capability report for the AI layer."""

    provider: Dict[str, Any]
    agents: List[str]
    supported_intents: List[str]
    suggested_questions: List[str]
    grounding: str
