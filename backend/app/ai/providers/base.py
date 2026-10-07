"""LLM provider abstraction.

The platform must work with or without an external language model. Every
provider receives the same grounded context and returns plain text; swapping
providers never changes what data the answer is based on.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """A generated answer plus the provenance needed for the UI."""

    text: str
    provider: str
    model: Optional[str] = None
    grounded: bool = True
    fallback_used: bool = False
    error: Optional[str] = None


class LLMProvider(abc.ABC):
    """Interface every provider implements."""

    name: str = "base"

    @abc.abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Produce an answer for the supplied prompts."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is configured and usable."""
