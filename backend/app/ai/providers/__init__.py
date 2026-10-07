"""Provider selection and safe invocation."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.ai.providers.base import LLMProvider, LLMResponse
from app.ai.providers.offline import OfflineProvider
from app.ai.providers.remote import (
    GeminiProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

_PROVIDERS = {
    "offline": OfflineProvider,
    "openai_compat": OpenAICompatibleProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


@lru_cache
def get_provider() -> LLMProvider:
    """Return the configured provider, falling back to offline when unusable."""
    factory = _PROVIDERS.get(settings.llm_provider, OfflineProvider)
    provider = factory()
    if not provider.is_available():
        logger.warning(
            "LLM provider '%s' is not configured; using the offline renderer.",
            settings.llm_provider,
        )
        return OfflineProvider()
    return provider


def generate(system_prompt: str, user_prompt: str) -> LLMResponse:
    """Generate an answer, degrading to the offline renderer on any failure."""
    provider = get_provider()
    if isinstance(provider, OfflineProvider):
        return provider.generate(system_prompt, user_prompt)

    try:
        return provider.generate(system_prompt, user_prompt)
    except Exception as exc:
        logger.warning("LLM provider '%s' failed: %s", provider.name, exc)
        response = OfflineProvider().generate(system_prompt, user_prompt)
        response.fallback_used = True
        response.error = f"{provider.name} unavailable: {type(exc).__name__}"
        return response


def provider_info() -> dict:
    provider = get_provider()
    return {
        "configured": settings.llm_provider,
        "active": provider.name,
        "model": getattr(provider, "model", None),
        "offline_fallback": isinstance(provider, OfflineProvider),
    }


__all__ = ["LLMProvider", "LLMResponse", "generate", "get_provider", "provider_info"]
