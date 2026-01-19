"""Base LLM client interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class LLMMessage:
    """Message in a conversation."""

    role: str
    content: Any


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: list[Any]
    stop_reason: str
    usage: Optional[dict] = None


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def create_message(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
        model: str,
    ) -> LLMResponse:
        """Create a message with the LLM."""
        pass
