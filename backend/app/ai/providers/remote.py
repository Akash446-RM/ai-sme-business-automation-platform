"""Remote LLM providers.

Three transports are supported behind one interface:

* ``openai_compat`` - OpenAI, Groq, OpenRouter, vLLM, LM Studio, any service
  exposing ``/chat/completions``
* ``gemini``        - Google Generative Language API
* ``ollama``        - a local Ollama server

Every provider degrades to the offline renderer if the call fails, so an
outage or an expired key never breaks the assistant.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.ai.providers.base import LLMProvider, LLMResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODELS = {
    "openai_compat": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.1",
}


class OpenAICompatibleProvider(LLMProvider):
    """Any service that speaks the OpenAI chat completions protocol."""

    name = "openai_compat"

    def __init__(self) -> None:
        self.api_key = settings.llm_api_key
        self.base_url = (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = settings.llm_model or DEFAULT_MODELS["openai_compat"]

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": settings.llm_max_output_tokens,
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        text = body["choices"][0]["message"]["content"].strip()
        return LLMResponse(text=text, provider=self.name, model=self.model)


class GeminiProvider(LLMProvider):
    """Google Generative Language API over plain HTTP (no extra SDK)."""

    name = "gemini"

    def __init__(self) -> None:
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model or DEFAULT_MODELS["gemini"]
        self.base_url = (
            settings.llm_base_url
            or "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": settings.llm_max_output_tokens,
            },
        }
        response = httpx.post(
            f"{self.base_url}/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        candidates = body.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise ValueError("Gemini returned an empty response")
        return LLMResponse(text=text, provider=self.name, model=self.model)


class OllamaProvider(LLMProvider):
    """Local Ollama server; no API key required."""

    name = "ollama"

    def __init__(self) -> None:
        self.base_url = (settings.llm_base_url or "http://localhost:11434").rstrip("/")
        self.model = settings.llm_model or DEFAULT_MODELS["ollama"]

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        text = response.json()["message"]["content"].strip()
        return LLMResponse(text=text, provider=self.name, model=self.model)
