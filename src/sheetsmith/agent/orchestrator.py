"""Agent orchestrator for handling user requests."""

import json
from typing import Any, Optional

from ..config import settings
from ..sheets import GoogleSheetsClient
from ..memory import MemoryStore
from ..tools import ToolRegistry, GSheetsTools, MemoryTools, FormulaTools
from ..engine import PatchEngine, FormulaDiffer
from ..llm import (
    AnthropicClient,
    OpenRouterClient,
    LLMClient,
    LLMCallLogger,
    BudgetGuard,
    calculate_message_chars,
    calculate_tools_size,
    estimate_tokens_from_chars,
)
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
        FormulaTools(self.sheets_client).register(self.registry)  # New formula tools

        # Add patch tools
        self._register_patch_tools()

        # Initialize LLM client based on provider
        self.client = self._create_llm_client()

        # Initialize cost tracking
        self.call_logger = LLMCallLogger(
            log_path=settings.cost_log_path,
            enabled=settings.enable_cost_logging,
        )
        self.budget_guard = BudgetGuard(
            payload_max_chars=settings.payload_max_chars,
            max_input_tokens=settings.max_input_tokens,
            per_request_budget_cents=settings.per_request_budget_cents,
            session_budget_cents=settings.session_budget_cents,
            alert_threshold_cents=settings.high_cost_threshold_cents,
        )

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

    def _preview_patch(self, spreadsheet_id: str, description: str, changes: list[dict]) -> dict:
        """Generate a patch preview."""
        patch = self.patch_engine.create_patch(
            spreadsheet_id=spreadsheet_id,
            description=description,
            changes=changes,
        )
        diff_string = patch.to_diff_string()

        # Calculate stats
        sheets = set()
        columns = set()
        for change in changes:
            sheets.add(change["sheet"])
            col = "".join(c for c in change["cell"] if c.isalpha())
            columns.add(col)

        return {
            "patch_id": patch.id,
            "description": description,
            "changes_count": len(changes),
            "diff": diff_string,
            "statistics": {
                "total_cells": len(changes),
                "affected_sheets": sorted(list(sheets)),
                "affected_columns": sorted(list(columns)),
                "sheet_count": len(sheets),
                "column_count": len(columns),
            },
            "message": (
                f"Review the diff above. This will update {len(changes)} cells "
                f"across {len(columns)} columns in {len(sheets)} sheet(s): "
                f"{', '.join(sorted(sheets))}. Reply 'apply' or 'approve' to apply these changes."
            ),
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

        # Prepare LLM call parameters
        tools = self.registry.to_anthropic_tools()
        
        # Pre-call cost checks
        message_chars = calculate_message_chars(self.messages)
        tools_size = calculate_tools_size(tools)
        system_chars = len(SYSTEM_PROMPT)
        total_chars = message_chars + system_chars
        
        # Check payload size
        try:
            self.budget_guard.check_payload_size(total_chars)
        except ValueError as e:
            # Return error to user instead of crashing
            return f"❌ Request rejected: {str(e)}"
        
        # Estimate tokens
        estimated_input_tokens = estimate_tokens_from_chars(total_chars + tools_size)
        estimated_output_tokens = settings.max_tokens
        
        # Check token limits
        try:
            self.budget_guard.check_token_limit(estimated_input_tokens)
        except ValueError as e:
            return f"❌ Request rejected: {str(e)}"
        
        # Check budget
        allowed, message = self.budget_guard.check_budget(
            model, estimated_input_tokens, estimated_output_tokens
        )
        if not allowed:
            return f"❌ Budget exceeded: {message}"
        
        # Show warning if high cost
        if message and settings.alert_on_high_cost:
            print(f"\n{message}\n")
        
        # Call LLM with tools
        response = self.client.create_message(
            model=model,
            max_tokens=settings.max_tokens,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=self.messages,
        )
        
        # Post-call logging
        usage = response.usage or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        actual_cost = self.budget_guard.estimate_cost(model, input_tokens, output_tokens)
        
        # Log the call
        self.call_logger.log_call(
            operation="process_message",
            model=model,
            provider=settings.llm_provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            message_chars=message_chars,
            tools_included=len(tools) > 0,
            tools_size_bytes=tools_size,
            max_tokens=settings.max_tokens,
            cost_cents=actual_cost,
            usage_data=usage,
        )
        
        # Update session cost
        self.budget_guard.update_session_cost(actual_cost)

        # Process response, handling tool calls
        return await self._process_response(response)

    async def _process_response(self, response) -> str:
        """Process LLM response, handling any tool calls."""
        assistant_content = []
        final_text = ""

        for block in response.content:
            # Handle both dict and object types
            block_type = (
                block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            )

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
            b
            for b in response.content
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

            # Prepare for continuation call
            tools = self.registry.to_anthropic_tools()
            
            # Pre-call cost checks for continuation
            message_chars = calculate_message_chars(self.messages)
            tools_size = calculate_tools_size(tools)
            system_chars = len(SYSTEM_PROMPT)
            total_chars = message_chars + system_chars
            
            # Estimate tokens for continuation
            estimated_input_tokens = estimate_tokens_from_chars(total_chars + tools_size)
            estimated_output_tokens = settings.max_tokens
            
            # Check budget for continuation
            allowed, message = self.budget_guard.check_budget(
                model, estimated_input_tokens, estimated_output_tokens
            )
            if not allowed:
                # Return partial response with budget warning
                return final_text + f"\n\n⚠️ Unable to continue: {message}"

            # Continue conversation
            continuation = self.client.create_message(
                model=model,
                max_tokens=settings.max_tokens,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=self.messages,
            )
            
            # Post-call logging for continuation
            usage = continuation.usage or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            actual_cost = self.budget_guard.estimate_cost(model, input_tokens, output_tokens)
            
            # Log the continuation call
            self.call_logger.log_call(
                operation="tool_continuation",
                model=model,
                provider=settings.llm_provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                message_chars=message_chars,
                tools_included=len(tools) > 0,
                tools_size_bytes=tools_size,
                max_tokens=settings.max_tokens,
                cost_cents=actual_cost,
                usage_data=usage,
            )
            
            # Update session cost
            self.budget_guard.update_session_cost(actual_cost)

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
    
    def reset_cost_tracking(self):
        """Reset cost tracking for the session."""
        self.call_logger.reset_session()
        self.budget_guard.reset_session()
    
    def get_cost_summary(self):
        """Get cost summary for the current session."""
        return {
            **self.call_logger.get_session_summary(),
            "budget_status": self.budget_guard.get_budget_status(),
        }
