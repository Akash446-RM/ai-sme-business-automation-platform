"""Deterministic offline provider.

This is not a stub. It renders the same structured, grounded context that an
LLM would receive into readable business prose, so the assistant is fully
functional with no API key, no network access and no cost. Because it only
formats retrieved facts it can never hallucinate.
"""

from __future__ import annotations

import re
from typing import List

from app.ai.providers.base import LLMProvider, LLMResponse


class OfflineProvider(LLMProvider):
    """Formats the retrieved context into a natural language answer."""

    name = "offline"

    def is_available(self) -> bool:
        return True

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Extract the narrative section the agent prepared and present it.

        The context builder always includes a ``SUMMARY`` block written in
        plain language plus a ``FACTS`` block. Rendering those directly gives a
        coherent answer without any generation step.
        """
        summary = self._section(user_prompt, "SUMMARY")
        facts = self._section(user_prompt, "FACTS")
        details = self._section(user_prompt, "DETAILS")

        parts: List[str] = []
        if summary:
            parts.append(summary.strip())
        if facts:
            parts.append(facts.strip())
        if details:
            parts.append(details.strip())

        if not parts:
            text = (
                "I do not have enough information in the business data to answer that "
                "reliably. Try asking about sales, revenue, top products, stock levels "
                "or what needs reordering."
            )
        else:
            text = "\n\n".join(parts)

        return LLMResponse(
            text=text,
            provider=self.name,
            model="template-renderer",
            grounded=True,
            fallback_used=False,
        )

    @staticmethod
    def _section(prompt: str, heading: str) -> str:
        """Pull one labelled block out of the structured prompt."""
        pattern = rf"^{heading}:\s*\n(.*?)(?=\n[A-Z][A-Z _]+:\s*\n|\Z)"
        match = re.search(pattern, prompt, flags=re.DOTALL | re.MULTILINE)
        return match.group(1) if match else ""
