"""Agent orchestrator for handling user requests."""

import json
from typing import Any, Optional

from ..config import settings
from ..sheets import GoogleSheetsClient
from ..memory import MemoryStore
from ..tools import ToolRegistry, GSheetsTools, MemoryTools
from ..engine import PatchEngine, FormulaDiffer
from ..llm import AnthropicClient, OpenRouterClient, LLMClient
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

        # Initialize LLM client based on provider
        self.client = self._create_llm_client()

        # Conversation history
        self.messages: list[dict] = []

    def _create_llm_client(self) -> LLMClient:
        """Create the appropriate LLM client based on configuration."""
        if settings.llm_provider == "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY is required when LLM_PROVIDER is 'openrouter'")
            return OpenRouterClient(api_key=settings.openrouter_api_key)
        else:
            # Default to Anthropic
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER is 'anthropic'")
            return AnthropicClient(api_key=settings.anthropic_api_key)

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

        # Determine the model to use
        model = (
            settings.openrouter_model 
            if settings.llm_provider == "openrouter" 
            else settings.model_name
        )

        # Call LLM with tools
        response = self.client.create_message(
            model=model,
            max_tokens=settings.max_tokens,
            system=SYSTEM_PROMPT,
            tools=self.registry.to_anthropic_tools(),
            messages=self.messages,
        )

        # Process response, handling tool calls
        return await self._process_response(response)

    async def _process_response(self, response) -> str:
        """Process LLM response, handling any tool calls."""
        assistant_content = []
        final_text = ""

        for block in response.content:
            # Handle both dict and object types
            block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            
            if block_type == "text":
                text = block.get("text") if isinstance(block, dict) else getattr(block, "text", "")
                final_text += text
                assistant_content.append(block)
            elif block_type == "tool_use":
                assistant_content.append(block)

        # Add assistant message to history
        self.messages.append({"role": "assistant", "content": assistant_content})

        # Handle tool calls
        tool_calls = [
            b for b in response.content 
            if (b.get("type") if isinstance(b, dict) else getattr(b, "type", None)) == "tool_use"
        ]
        if tool_calls and response.stop_reason == "tool_use":
            tool_results = []
            for tool_call in tool_calls:
                # Handle both dict and object types
                if isinstance(tool_call, dict):
                    name = tool_call["name"]
                    input_data = tool_call["input"]
                    tool_id = tool_call["id"]
                else:
                    name = tool_call.name
                    input_data = tool_call.input
                    tool_id = tool_call.id
                    
                result = await self._execute_tool(name, input_data)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result, default=str),
                    }
                )

            # Add tool results to messages
            self.messages.append({"role": "user", "content": tool_results})

            # Determine the model to use
            model = (
                settings.openrouter_model 
                if settings.llm_provider == "openrouter" 
                else settings.model_name
            )

            # Continue conversation
            continuation = self.client.create_message(
                model=model,
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
