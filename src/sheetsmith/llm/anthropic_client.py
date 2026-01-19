"""Anthropic LLM client."""

from typing import Any
from anthropic import Anthropic

from .base import LLMClient, LLMResponse


class AnthropicClient(LLMClient):
    """Anthropic Claude client."""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)

    def create_message(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
        model: str,
    ) -> LLMResponse:
        """Create a message with Claude."""
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        
        return LLMResponse(
            content=response.content,
            stop_reason=response.stop_reason,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        )
