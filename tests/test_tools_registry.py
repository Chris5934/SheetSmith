"""Tests for the tool registry."""

from unittest.mock import AsyncMock, Mock

import pytest

from sheetsmith.tools.registry import Tool, ToolParameter, ToolRegistry


class TestToolParameter:
    """Test ToolParameter model."""

    def test_tool_parameter_creation_required(self):
        """Test creating a required tool parameter."""
        param = ToolParameter(
            name="spreadsheet_id",
            type="string",
            description="The ID of the spreadsheet",
            required=True,
        )
        
        assert param.name == "spreadsheet_id"
        assert param.type == "string"
        assert param.description == "The ID of the spreadsheet"
        assert param.required is True
        assert param.default is None
        assert param.enum is None

    def test_tool_parameter_creation_optional(self):
        """Test creating an optional tool parameter with default."""
        param = ToolParameter(
            name="sheet_name",
            type="string",
            description="The name of the sheet",
            required=False,
            default="Sheet1",
        )
        
        assert param.required is False
        assert param.default == "Sheet1"

    def test_tool_parameter_with_enum(self):
        """Test creating a parameter with enum values."""
        param = ToolParameter(
            name="action",
            type="string",
            description="Action to perform",
            required=True,
            enum=["read", "write", "delete"],
        )
        
        assert param.enum == ["read", "write", "delete"]


class TestTool:
    """Test Tool model."""

    def test_tool_creation_basic(self):
        """Test creating a basic tool."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
        )
        
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.parameters == []
        assert tool.handler is None

    def test_tool_with_parameters(self):
        """Test creating a tool with parameters."""
        params = [
            ToolParameter(name="arg1", type="string", description="First argument"),
            ToolParameter(name="arg2", type="integer", description="Second argument"),
        ]
        
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters=params,
        )
        
        assert len(tool.parameters) == 2
        assert tool.parameters[0].name == "arg1"
        assert tool.parameters[1].name == "arg2"

    def test_tool_with_handler(self):
        """Test creating a tool with a handler function."""
        def handler(arg1: str) -> str:
            return f"Handled: {arg1}"
        
        tool = Tool(
            name="test_tool",
            description="A test tool",
            handler=handler,
        )
        
        assert tool.handler is not None
        assert callable(tool.handler)

    def test_tool_to_anthropic_schema_basic(self):
        """Test converting tool to Anthropic schema format."""
        tool = Tool(
            name="read_sheet",
            description="Read data from a sheet",
            parameters=[
                ToolParameter(
                    name="spreadsheet_id",
                    type="string",
                    description="The spreadsheet ID",
                    required=True,
                ),
            ],
        )
        
        schema = tool.to_anthropic_schema()
        
        assert schema["name"] == "read_sheet"
        assert schema["description"] == "Read data from a sheet"
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"
        assert "spreadsheet_id" in schema["input_schema"]["properties"]
        assert "spreadsheet_id" in schema["input_schema"]["required"]

    def test_tool_to_anthropic_schema_with_optional_params(self):
        """Test Anthropic schema with optional parameters."""
        tool = Tool(
            name="update_cell",
            description="Update a cell value",
            parameters=[
                ToolParameter(
                    name="cell",
                    type="string",
                    description="Cell notation",
                    required=True,
                ),
                ToolParameter(
                    name="value",
                    type="string",
                    description="New value",
                    required=False,
                    default="",
                ),
            ],
        )
        
        schema = tool.to_anthropic_schema()
        
        assert "cell" in schema["input_schema"]["required"]
        assert "value" not in schema["input_schema"]["required"]
        assert schema["input_schema"]["properties"]["value"]["default"] == ""

    def test_tool_to_anthropic_schema_with_enum(self):
        """Test Anthropic schema with enum parameter."""
        tool = Tool(
            name="search",
            description="Search for data",
            parameters=[
                ToolParameter(
                    name="search_type",
                    type="string",
                    description="Type of search",
                    required=True,
                    enum=["exact", "fuzzy", "regex"],
                ),
            ],
        )
        
        schema = tool.to_anthropic_schema()
        
        assert "enum" in schema["input_schema"]["properties"]["search_type"]
        assert schema["input_schema"]["properties"]["search_type"]["enum"] == [
            "exact",
            "fuzzy",
            "regex",
        ]


class TestToolRegistry:
    """Test ToolRegistry functionality."""

    def test_registry_initialization(self):
        """Test that registry initializes empty."""
        registry = ToolRegistry()
        
        assert registry.list_tools() == []

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = Tool(name="test_tool", description="Test")
        
        registry.register(tool)
        
        assert len(registry.list_tools()) == 1
        assert registry.get("test_tool") == tool

    def test_register_multiple_tools(self):
        """Test registering multiple tools."""
        registry = ToolRegistry()
        tool1 = Tool(name="tool1", description="First tool")
        tool2 = Tool(name="tool2", description="Second tool")
        
        registry.register(tool1)
        registry.register(tool2)
        
        assert len(registry.list_tools()) == 2
        assert registry.get("tool1") == tool1
        assert registry.get("tool2") == tool2

    def test_get_tool_by_name(self):
        """Test retrieving a tool by name."""
        registry = ToolRegistry()
        tool = Tool(name="my_tool", description="Test")
        registry.register(tool)
        
        retrieved = registry.get("my_tool")
        
        assert retrieved is not None
        assert retrieved.name == "my_tool"

    def test_get_nonexistent_tool_returns_none(self):
        """Test that getting nonexistent tool returns None."""
        registry = ToolRegistry()
        
        result = registry.get("nonexistent")
        
        assert result is None

    def test_list_all_tools(self):
        """Test listing all registered tools."""
        registry = ToolRegistry()
        tools = [
            Tool(name="tool1", description="First"),
            Tool(name="tool2", description="Second"),
            Tool(name="tool3", description="Third"),
        ]
        
        for tool in tools:
            registry.register(tool)
        
        all_tools = registry.list_tools()
        
        assert len(all_tools) == 3
        assert all(isinstance(t, Tool) for t in all_tools)

    def test_to_anthropic_tools(self):
        """Test converting all tools to Anthropic format."""
        registry = ToolRegistry()
        tool1 = Tool(name="tool1", description="First tool")
        tool2 = Tool(name="tool2", description="Second tool")
        
        registry.register(tool1)
        registry.register(tool2)
        
        anthropic_tools = registry.to_anthropic_tools()
        
        assert len(anthropic_tools) == 2
        assert all(isinstance(t, dict) for t in anthropic_tools)
        assert anthropic_tools[0]["name"] == "tool1"
        assert anthropic_tools[1]["name"] == "tool2"

    @pytest.mark.asyncio
    async def test_execute_sync_tool(self):
        """Test executing a synchronous tool."""
        def sync_handler(arg: str) -> str:
            return f"Result: {arg}"
        
        registry = ToolRegistry()
        tool = Tool(name="sync_tool", description="Sync", handler=sync_handler)
        registry.register(tool)
        
        result = await registry.execute("sync_tool", arg="test")
        
        assert result == "Result: test"

    @pytest.mark.asyncio
    async def test_execute_async_tool(self):
        """Test executing an asynchronous tool."""
        async def async_handler(arg: str) -> str:
            return f"Async result: {arg}"
        
        registry = ToolRegistry()
        tool = Tool(name="async_tool", description="Async", handler=async_handler)
        registry.register(tool)
        
        result = await registry.execute("async_tool", arg="test")
        
        assert result == "Async result: test"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool_raises_error(self):
        """Test that executing nonexistent tool raises ValueError."""
        registry = ToolRegistry()
        
        with pytest.raises(ValueError, match="Unknown tool"):
            await registry.execute("nonexistent_tool")

    @pytest.mark.asyncio
    async def test_execute_tool_without_handler_raises_error(self):
        """Test that executing tool without handler raises ValueError."""
        registry = ToolRegistry()
        tool = Tool(name="no_handler", description="No handler")
        registry.register(tool)
        
        with pytest.raises(ValueError, match="has no handler"):
            await registry.execute("no_handler")

    def test_registry_overwrites_duplicate_names(self):
        """Test that registering a tool with same name overwrites."""
        registry = ToolRegistry()
        tool1 = Tool(name="tool", description="First")
        tool2 = Tool(name="tool", description="Second")
        
        registry.register(tool1)
        registry.register(tool2)
        
        assert len(registry.list_tools()) == 1
        assert registry.get("tool").description == "Second"
