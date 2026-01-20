"""Tests for OpenRouter client."""

import json
import pytest
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
        # Verify it's not Python str() format (which would start with "{'")
        assert not arguments_str.lstrip().startswith("{'")

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

    def test_convert_tools_replaces_dots_with_underscores(self):
        """Test that tool names with dots are converted to underscores."""
        client = OpenRouterClient(api_key="test-key")

        anthropic_tools = [
            {
                "name": "gsheets.read_range",
                "description": "Read from a range",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID"}
                    },
                    "required": ["spreadsheet_id"],
                },
            },
            {
                "name": "memory.store_rule",
                "description": "Store a rule",
                "input_schema": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "Rule name"}},
                    "required": ["name"],
                },
            },
        ]

        result = client._convert_tools(anthropic_tools)

        assert len(result) == 2
        assert result[0]["function"]["name"] == "gsheets_read_range"
        assert result[1]["function"]["name"] == "memory_store_rule"

        # Verify mapping is stored
        assert client._tool_name_map["gsheets_read_range"] == "gsheets.read_range"
        assert client._tool_name_map["memory_store_rule"] == "memory.store_rule"

    def test_convert_tools_adds_items_to_array_parameters(self):
        """Test that array parameters get an items field."""
        client = OpenRouterClient(api_key="test-key")

        anthropic_tools = [
            {
                "name": "test.tool",
                "description": "Test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sheet_names": {
                            "type": "array",
                            "description": "List of sheet names",
                        },
                        "tags": {
                            "type": "array",
                            "description": "Tags",
                        },
                        "count": {
                            "type": "integer",
                            "description": "A count",
                        },
                    },
                    "required": ["sheet_names"],
                },
            }
        ]

        result = client._convert_tools(anthropic_tools)

        assert len(result) == 1
        params = result[0]["function"]["parameters"]

        # Verify array parameters have items field
        assert "items" in params["properties"]["sheet_names"]
        assert params["properties"]["sheet_names"]["items"] == {"type": "string"}
        assert "items" in params["properties"]["tags"]
        assert params["properties"]["tags"]["items"] == {"type": "string"}

        # Verify non-array parameters are unchanged
        assert "items" not in params["properties"]["count"]

    def test_convert_response_maps_tool_names_back(self):
        """Test that tool names are converted back from underscores to dots."""
        client = OpenRouterClient(api_key="test-key")

        # First set up the name mappings as they would be after _convert_tools
        client._tool_name_map["gsheets_read_range"] = "gsheets.read_range"
        client._tool_name_map["memory_store_rule"] = "memory.store_rule"

        # Simulate OpenRouter response with underscore names
        openrouter_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "I'll help with that.",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "gsheets_read_range",
                                    "arguments": '{"spreadsheet_id": "abc123", "range": "A1:B10"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        result = client._convert_response(openrouter_response)

        # Find tool_use block
        tool_use_block = None
        for block in result.content:
            if block.get("type") == "tool_use":
                tool_use_block = block
                break

        assert tool_use_block is not None
        # Verify name was converted back to dot notation
        assert tool_use_block["name"] == "gsheets.read_range"
        assert tool_use_block["input"] == {"spreadsheet_id": "abc123", "range": "A1:B10"}

    def test_convert_messages_converts_tool_use_names_to_underscores(self):
        """Test that tool_use in messages are converted to underscore names."""
        client = OpenRouterClient(api_key="test-key")

        # Set up reverse mapping as it would be after _convert_tools
        client._tool_name_reverse_map["gsheets.read_range"] = "gsheets_read_range"

        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Reading the data."},
                    {
                        "type": "tool_use",
                        "id": "call_456",
                        "name": "gsheets.read_range",
                        "input": {"spreadsheet_id": "xyz789"},
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

        assert msg_with_tools is not None
        assert len(msg_with_tools["tool_calls"]) == 1

        # Verify name was converted to underscore notation
        tool_call = msg_with_tools["tool_calls"][0]
        assert tool_call["function"]["name"] == "gsheets_read_range"

    def test_fix_array_parameters_preserves_existing_items(self):
        """Test that existing items field is preserved."""
        client = OpenRouterClient(api_key="test-key")

        schema = {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "description": "List of updates",
                    "items": {"type": "object"},
                },
            },
        }

        result = client._fix_array_parameters(schema)

        # Verify existing items field is preserved
        assert result["properties"]["updates"]["items"] == {"type": "object"}

    def test_fix_array_parameters_preserves_other_schema_fields(self):
        """Test that other schema fields like 'required' are preserved."""
        client = OpenRouterClient(api_key="test-key")

        schema = {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "description": "List of names",
                },
            },
            "required": ["names"],
        }

        result = client._fix_array_parameters(schema)

        # Verify required field is preserved
        assert "required" in result
        assert result["required"] == ["names"]
        # Verify items was added
        assert result["properties"]["names"]["items"] == {"type": "string"}

    def test_convert_tools_raises_error_on_missing_name(self):
        """Test that converting tools without names raises an error."""
        client = OpenRouterClient(api_key="test-key")

        tools_without_name = [
            {
                "description": "A tool without a name",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        with pytest.raises(ValueError, match="must have a 'name' field"):
            client._convert_tools(tools_without_name)
