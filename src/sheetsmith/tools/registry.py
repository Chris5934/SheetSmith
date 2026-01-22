"""Tool registry for managing available tools."""

from typing import Any, Callable, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolParameter(BaseModel):
    """Definition of a tool parameter."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[list[str]] = None


class Tool(BaseModel):
    """Definition of a tool that can be used by the agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)
    handler: Optional[Callable] = Field(default=None, exclude=True)

    def to_anthropic_schema(self) -> dict:
        """Convert to Anthropic tool schema format."""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


class ToolRegistry:
    """Registry for managing tools available to the agent."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def to_anthropic_tools(self) -> list[dict]:
        """Convert all tools to Anthropic format."""
        return [tool.to_anthropic_schema() for tool in self._tools.values()]

    async def execute(self, tool_name: str, **kwargs) -> Any:
        """Execute a tool by name."""
        tool = self.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        if not tool.handler:
            raise ValueError(f"Tool {tool_name} has no handler")

        import asyncio

        if asyncio.iscoroutinefunction(tool.handler):
            return await tool.handler(**kwargs)
        return tool.handler(**kwargs)
