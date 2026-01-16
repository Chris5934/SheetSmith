"""Agent orchestrator for handling user requests."""

import json
from typing import Any, Optional

from anthropic import Anthropic

from ..config import settings
from ..sheets import GoogleSheetsClient
from ..memory import MemoryStore
from ..tools import ToolRegistry, GSheetsTools, MemoryTools
from ..engine import PatchEngine, FormulaDiffer
from .prompts import SYSTEM_PROMPT


class SheetSmithAgent:
    """Orchestrates the SheetSmith agent using Claude."""

    def __init__(
        self,
        sheets_client: Optional[GoogleSheetsClient] = None,
        memory_store: Optional[MemoryStore] = None,
    ):
        self.sheets_client = sheets_client or GoogleSheetsClient()
        self.memory_store = memory_store or MemoryStore()
        self.patch_engine = PatchEngine(self.sheets_client, self.memory_store)
        self.differ = FormulaDiffer()

        # Set up tools
        self.registry = ToolRegistry()
        GSheetsTools(self.sheets_client).register(self.registry)
        MemoryTools(self.memory_store).register(self.registry)

        # Add patch tools
        self._register_patch_tools()

        # Initialize Anthropic client
        self.client = Anthropic(api_key=settings.anthropic_api_key)

        # Conversation history
        self.messages: list[dict] = []

    def _register_patch_tools(self):
        """Register patch-related tools."""
        from ..tools.registry import Tool, ToolParameter

        # Preview patch tool
        self.registry.register(
            Tool(
                name="patch.preview",
                description="Generate a diff preview of proposed formula changes before applying them.",
                parameters=[
                    ToolParameter(
                        name="spreadsheet_id",
                        type="string",
                        description="The spreadsheet ID",
                    ),
                    ToolParameter(
                        name="description",
                        type="string",
                        description="Description of the changes",
                    ),
                    ToolParameter(
                        name="changes",
                        type="array",
                        description="List of changes: [{sheet, cell, old, new}, ...]",
                    ),
                ],
                handler=self._preview_patch,
            )
        )

        # Apply patch tool
        self.registry.register(
            Tool(
                name="patch.apply",
                description="Apply a previously created patch. Only call this after user has approved the changes.",
                parameters=[
                    ToolParameter(
                        name="patch_id",
                        type="string",
                        description="The ID of the patch to apply",
                    ),
                ],
                handler=self._apply_patch,
            )
        )

    def _preview_patch(
        self, spreadsheet_id: str, description: str, changes: list[dict]
    ) -> dict:
        """Generate a patch preview."""
        patch = self.patch_engine.create_patch(
            spreadsheet_id=spreadsheet_id,
            description=description,
            changes=changes,
        )
        diff_string = patch.to_diff_string()
        return {
            "patch_id": patch.id,
            "description": description,
            "changes_count": len(changes),
            "diff": diff_string,
            "message": "Review the diff above. Reply 'apply' or 'approve' to apply these changes.",
        }

    async def _apply_patch(self, patch_id: str) -> dict:
        """Apply a patch."""
        return await self.patch_engine.apply_patch(patch_id, user_approved=True)

    async def initialize(self):
        """Initialize the agent (database, etc.)."""
        await self.memory_store.initialize()

    async def shutdown(self):
        """Shutdown the agent."""
        await self.memory_store.close()

    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the agent's response."""
        self.messages.append({"role": "user", "content": user_message})

        # Call Claude with tools
        response = self.client.messages.create(
            model=settings.model_name,
            max_tokens=settings.max_tokens,
            system=SYSTEM_PROMPT,
            tools=self.registry.to_anthropic_tools(),
            messages=self.messages,
        )

        # Process response, handling tool calls
        return await self._process_response(response)

    async def _process_response(self, response) -> str:
        """Process Claude's response, handling any tool calls."""
        assistant_content = []
        final_text = ""

        for block in response.content:
            if block.type == "text":
                final_text += block.text
                assistant_content.append(block)
            elif block.type == "tool_use":
                assistant_content.append(block)

        # Add assistant message to history
        self.messages.append({"role": "assistant", "content": assistant_content})

        # Handle tool calls
        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if tool_calls and response.stop_reason == "tool_use":
            tool_results = []
            for tool_call in tool_calls:
                result = await self._execute_tool(tool_call.name, tool_call.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps(result, default=str),
                    }
                )

            # Add tool results to messages
            self.messages.append({"role": "user", "content": tool_results})

            # Continue conversation
            continuation = self.client.messages.create(
                model=settings.model_name,
                max_tokens=settings.max_tokens,
                system=SYSTEM_PROMPT,
                tools=self.registry.to_anthropic_tools(),
                messages=self.messages,
            )

            return await self._process_response(continuation)

        return final_text

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Execute a tool and return its result."""
        try:
            result = await self.registry.execute(tool_name, **tool_input)
            return result
        except Exception as e:
            return {"error": str(e)}

    def reset_conversation(self):
        """Reset the conversation history."""
        self.messages = []
