"""OpenRouter LLM client."""

import json
import httpx

from .base import LLMClient, LLMResponse


class OpenRouterClient(LLMClient):
    """OpenRouter HTTP API client."""

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url

    def create_message(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int,
        model: str,
    ) -> LLMResponse:
        """Create a message via OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Chris5934/SheetSmith",
            "X-Title": "SheetSmith",
        }

        # Convert Anthropic-style messages to OpenRouter format
        openrouter_messages = self._convert_messages(messages, system)

        payload = {
            "model": model,
            "messages": openrouter_messages,
            "max_tokens": max_tokens,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = self._convert_tools(tools)

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        # Convert OpenRouter response to our format
        return self._convert_response(data)

    def _convert_messages(self, messages: list[dict], system: str) -> list[dict]:
        """Convert Anthropic-style messages to OpenRouter format."""
        openrouter_messages = []

        # Add system message at the start
        if system:
            openrouter_messages.append(
                {
                    "role": "system",
                    "content": system,
                }
            )

        # Convert messages
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Handle different content types
            if isinstance(content, str):
                openrouter_messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )
            elif isinstance(content, list):
                # For complex content with tool calls/results
                text_parts = []
                tool_calls = []

                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                        elif item.get("type") == "tool_use":
                            tool_calls.append(
                                {
                                    "id": item.get("id"),
                                    "type": "function",
                                    "function": {
                                        "name": item.get("name"),
                                        "arguments": json.dumps(item.get("input", {})),
                                    },
                                }
                            )
                        elif item.get("type") == "tool_result":
                            # Tool results go in a separate message
                            openrouter_messages.append(
                                {
                                    "role": "tool",
                                    "content": item.get("content", ""),
                                    "tool_call_id": item.get("tool_use_id"),
                                }
                            )
                    elif hasattr(item, "type"):
                        # Handle Anthropic SDK objects
                        if item.type == "text":
                            text_parts.append(item.text)
                        elif item.type == "tool_use":
                            tool_calls.append(
                                {
                                    "id": item.id,
                                    "type": "function",
                                    "function": {
                                        "name": item.name,
                                        "arguments": json.dumps(item.input),
                                    },
                                }
                            )

                # Add message with text and/or tool calls
                if text_parts or (role == "assistant" and tool_calls):
                    msg_dict = {
                        "role": role,
                        "content": " ".join(text_parts) if text_parts else "",
                    }
                    if tool_calls:
                        msg_dict["tool_calls"] = tool_calls
                    if msg_dict["content"] or tool_calls:
                        openrouter_messages.append(msg_dict)

        return openrouter_messages

    def _convert_tools(self, anthropic_tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenRouter/OpenAI format."""
        openrouter_tools = []

        for tool in anthropic_tools:
            openrouter_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description"),
                        "parameters": tool.get("input_schema", {}),
                    },
                }
            )

        return openrouter_tools

    def _convert_response(self, data: dict) -> LLMResponse:
        """Convert OpenRouter response to our format."""
        choice = data["choices"][0]
        message = choice["message"]

        # Build content blocks similar to Anthropic format
        content = []

        # Add text content if present
        if message.get("content"):
            content.append(
                {
                    "type": "text",
                    "text": message["content"],
                }
            )

        # Add tool calls if present
        if message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "input": json.loads(tool_call["function"]["arguments"]),
                    }
                )

        # Determine stop reason
        finish_reason = choice.get("finish_reason", "stop")
        stop_reason_map = {
            "tool_calls": "tool_use",
            "stop": "end_turn",
            "length": "max_tokens",
        }
        stop_reason = stop_reason_map.get(finish_reason, finish_reason)

        # Extract usage info if available
        usage = None
        if "usage" in data:
            usage = {
                "input_tokens": data["usage"].get("prompt_tokens", 0),
                "output_tokens": data["usage"].get("completion_tokens", 0),
            }

        return LLMResponse(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
        )
