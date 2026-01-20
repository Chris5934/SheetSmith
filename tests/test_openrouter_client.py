"""Tests for OpenRouter client."""

import json
from unittest.mock import Mock

from sheetsmith.llm.openrouter_client import OpenRouterClient


class TestOpenRouterClient:
    """Tests for OpenRouterClient."""

    def test_convert_messages_with_dict_tool_use_arguments_json_serialization(self):
        """Test that tool_use arguments are properly JSON serialized when from dict."""
        client = OpenRouterClient(api_key="test-key")

        # Create a message with tool_use that has dict input
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me help you with that."},
                    {
                        "type": "tool_use",
                        "id": "call_123",
                        "name": "read_range",
                        "input": {"range": "A1:B10", "sheet_name": "Sheet1"},
                    },
                ],
            }
        ]

        result = client._convert_messages(messages, "")

        # Find the message with tool_calls
        msg_with_tools = None
        for msg in result:
            if msg.get("tool_calls"):
                msg_with_tools = msg
                break

        assert msg_with_tools is not None, "Expected to find message with tool_calls"
        assert len(msg_with_tools["tool_calls"]) == 1

        tool_call = msg_with_tools["tool_calls"][0]
        arguments_str = tool_call["function"]["arguments"]

        # Verify it's valid JSON
        parsed_args = json.loads(arguments_str)
        assert parsed_args == {"range": "A1:B10", "sheet_name": "Sheet1"}
        # Verify it's not Python str() format (which would have single quotes)
        assert "'" not in arguments_str  # JSON uses double quotes

    def test_convert_messages_with_object_tool_use_arguments_json_serialization(self):
        """Test that tool_use arguments are properly JSON serialized when from object."""
        client = OpenRouterClient(api_key="test-key")

        # Create a mock object similar to Anthropic SDK objects
        mock_text_item = Mock()
        mock_text_item.type = "text"
        mock_text_item.text = "I'll read the data."

        mock_tool_item = Mock()
        mock_tool_item.type = "tool_use"
        mock_tool_item.id = "call_456"
        mock_tool_item.name = "update_cell"
        mock_tool_item.input = {"cell": "A1", "value": "New Value", "sheet_id": 123}

        messages = [
            {
                "role": "assistant",
                "content": [mock_text_item, mock_tool_item],
            }
        ]

        result = client._convert_messages(messages, "")

        # Find the message with tool_calls
        msg_with_tools = None
        for msg in result:
            if msg.get("tool_calls"):
                msg_with_tools = msg
                break

        assert msg_with_tools is not None, "Expected to find message with tool_calls"
        assert len(msg_with_tools["tool_calls"]) == 1

        tool_call = msg_with_tools["tool_calls"][0]
        arguments_str = tool_call["function"]["arguments"]

        # Verify it's valid JSON
        parsed_args = json.loads(arguments_str)
        assert parsed_args == {"cell": "A1", "value": "New Value", "sheet_id": 123}
        # Verify it's not Python str() format
        assert "'" not in arguments_str  # JSON uses double quotes

    def test_convert_messages_with_empty_input_json_serialization(self):
        """Test that empty input is properly JSON serialized as {}."""
        client = OpenRouterClient(api_key="test-key")

        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_789",
                        "name": "list_sheets",
                        "input": {},
                    },
                ],
            }
        ]

        result = client._convert_messages(messages, "")

        msg_with_tools = None
        for msg in result:
            if msg.get("tool_calls"):
                msg_with_tools = msg
                break

        assert msg_with_tools is not None
        tool_call = msg_with_tools["tool_calls"][0]
        arguments_str = tool_call["function"]["arguments"]

        # Verify it's valid JSON for empty object
        parsed_args = json.loads(arguments_str)
        assert parsed_args == {}
        assert arguments_str == "{}"  # Proper JSON empty object

    def test_convert_messages_with_nested_objects_json_serialization(self):
        """Test that nested objects in tool arguments are properly JSON serialized."""
        client = OpenRouterClient(api_key="test-key")

        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_complex",
                        "name": "complex_tool",
                        "input": {
                            "data": {"nested": {"key": "value"}},
                            "list": [1, 2, 3],
                            "string": "test",
                        },
                    },
                ],
            }
        ]

        result = client._convert_messages(messages, "")

        msg_with_tools = None
        for msg in result:
            if msg.get("tool_calls"):
                msg_with_tools = msg
                break

        assert msg_with_tools is not None
        tool_call = msg_with_tools["tool_calls"][0]
        arguments_str = tool_call["function"]["arguments"]

        # Verify it's valid JSON with proper structure
        parsed_args = json.loads(arguments_str)
        assert parsed_args["data"]["nested"]["key"] == "value"
        assert parsed_args["list"] == [1, 2, 3]
        assert parsed_args["string"] == "test"
