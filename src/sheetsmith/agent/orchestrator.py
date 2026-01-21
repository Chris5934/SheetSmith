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
    OperationBudgetGuard,
    OperationType,
    PARSER_SYSTEM_PROMPT,
    AI_ASSIST_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
    calculate_message_chars,
    calculate_tools_size,
    estimate_tokens_from_chars,
    LLMDiagnostics,
    CostSpikeDetector,
    DiagnosticAlertSystem,
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
        self.operation_budget_guard = OperationBudgetGuard()
        
        # Initialize diagnostics system
        self.diagnostics = LLMDiagnostics(
            max_system_prompt_chars=settings.max_system_prompt_chars,
            max_history_messages=settings.max_history_messages,
            max_sheet_content_chars=settings.max_sheet_content_chars,
            max_tools_schema_bytes=settings.max_tools_schema_bytes,
            spike_detector=CostSpikeDetector(
                threshold_multiplier=settings.cost_spike_threshold_multiplier
            ),
        )
        self.alert_system = DiagnosticAlertSystem(
            enabled=settings.enable_cost_spike_detection
        )
        
        # Store diagnostic reports for API access
        self.diagnostic_reports: list = []

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

    def _detect_operation_type(self, user_message: str) -> OperationType:
        """Detect the operation type from user message.
        
        Args:
            user_message: The user's message
            
        Returns:
            The detected operation type
        """
        # Simple heuristics for operation detection
        msg_lower = user_message.lower()
        
        # Keywords indicating planning/complex operations
        planning_keywords = ["search", "find", "show me", "what", "which", "where", "audit", "list"]
        if any(keyword in msg_lower for keyword in planning_keywords):
            return "planning"
        
        # Keywords indicating simple operations
        parser_keywords = ["replace", "change", "update", "fix", "set"]
        if any(keyword in msg_lower for keyword in parser_keywords):
            return "parser"
        
        # Default to ai_assist for ambiguous requests
        return "ai_assist"
    
    def _get_context_for_llm(self, operation: OperationType) -> list[dict]:
        """Get minimal context based on operation type.
        
        Args:
            operation: The operation type
            
        Returns:
            List of messages to send to LLM
        """
        if operation == "parser":
            # Parser is stateless - only send current message
            return self.messages[-1:] if self.messages else []
        elif operation == "ai_assist":
            # AI assist keeps last 2-3 exchanges (4-6 messages)
            return self.messages[-6:]
        else:
            # Planning mode keeps more context but still limited
            return self.messages[-10:]
    
    def _get_system_prompt(self, operation: OperationType) -> str:
        """Get system prompt based on operation type.
        
        Args:
            operation: The operation type
            
        Returns:
            System prompt string
        """
        if operation == "parser":
            return PARSER_SYSTEM_PROMPT
        elif operation == "ai_assist":
            return AI_ASSIST_SYSTEM_PROMPT
        elif operation == "planning":
            return PLANNING_SYSTEM_PROMPT
        else:
            # Fallback to full prompt for complex operations
            return SYSTEM_PROMPT
    
    def _get_model_for_operation(self, operation: OperationType) -> str:
        """Get the appropriate model for an operation type.
        
        Args:
            operation: The operation type
            
        Returns:
            Model name to use
        """
        if settings.llm_provider == "openrouter":
            # Use operation-specific models for OpenRouter
            base_model = settings.openrouter_model
            if operation == "parser" and settings.parser_model:
                base_model = settings.parser_model
            elif operation == "ai_assist" and settings.ai_assist_model:
                base_model = settings.ai_assist_model
            
            # Add :free suffix if enabled
            if settings.use_free_models and ":free" not in base_model:
                base_model = f"{base_model}:free"
            
            return base_model
        else:
            # Anthropic doesn't have free models, use Haiku for parser/assist
            if operation == "parser" or operation == "ai_assist":
                return "claude-3-haiku-20240307"
            return settings.model_name
    
    def _get_max_tokens_for_operation(self, operation: OperationType) -> int:
        """Get max_tokens setting for an operation type.
        
        Args:
            operation: The operation type
            
        Returns:
            Maximum tokens to generate
        """
        if operation == "parser":
            return settings.parser_max_tokens
        elif operation == "ai_assist":
            return settings.ai_assist_max_tokens
        elif operation == "planning":
            return settings.planning_max_tokens
        else:
            return settings.max_tokens

    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the agent's response."""
        self.messages.append({"role": "user", "content": user_message})

        # Detect operation type based on message content
        operation: OperationType = self._detect_operation_type(user_message)
        
        # Get operation-specific settings
        model = self._get_model_for_operation(operation)
        max_tokens = self._get_max_tokens_for_operation(operation)
        system_prompt = self._get_system_prompt(operation)
        context_messages = self._get_context_for_llm(operation)
        
        # Prepare tools - only use them if NOT in JSON mode or if operation requires it
        tools = []
        if not settings.use_json_mode or operation in ["planning", "tool_continuation"]:
            tools = self.registry.to_anthropic_tools()
        
        # Pre-call cost checks
        message_chars = calculate_message_chars(context_messages)
        tools_size = calculate_tools_size(tools)
        system_chars = len(system_prompt)
        total_chars = message_chars + system_chars
        
        # Validate prompt size against hard cap
        if total_chars > settings.prompt_max_chars:
            return (
                f"❌ Request too large: {total_chars} chars exceeds limit of "
                f"{settings.prompt_max_chars} chars. Please shorten your request."
            )
        
        # Check payload size
        try:
            self.budget_guard.check_payload_size(total_chars)
        except ValueError as e:
            return f"❌ Request rejected: {str(e)}"
        
        # Estimate tokens
        estimated_input_tokens = estimate_tokens_from_chars(total_chars + tools_size)
        estimated_output_tokens = max_tokens
        
        # Check token limits
        try:
            self.budget_guard.check_token_limit(estimated_input_tokens)
        except ValueError as e:
            return f"❌ Request rejected: {str(e)}"
        
        # Estimate cost
        estimated_cost = self.budget_guard.estimate_cost(
            model, estimated_input_tokens, estimated_output_tokens
        )
        
        # Check operation-specific budget
        allowed, error_msg = self.operation_budget_guard.check_operation_budget(
            operation, estimated_cost, estimated_input_tokens
        )
        if not allowed:
            return f"❌ {error_msg}"
        
        # Check overall budget
        allowed, message = self.budget_guard.check_budget(
            model, estimated_input_tokens, estimated_output_tokens
        )
        if not allowed:
            return f"❌ Budget exceeded: {message}"
        
        # Show warning if high cost
        if message and settings.alert_on_high_cost:
            print(f"\n{message}\n")
        
        # Pre-call diagnostic check
        import time
        payload = {
            "model": model,
            "system": system_prompt,
            "messages": context_messages,
            "tools": tools,
            "max_tokens": max_tokens,
        }
        expected_model = self._get_model_for_operation(operation)
        pre_report = self.diagnostics.pre_call_check(payload, operation, expected_model)
        
        # Block call if there are errors
        if pre_report.errors:
            return f"❌ Diagnostic check failed: {', '.join(pre_report.errors)}"
        
        # Call LLM with or without tools
        start_time = time.time()
        response = self.client.create_message(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tools,
            messages=context_messages,
        )
        duration = (time.time() - start_time) * 1000  # Convert to ms
        
        # Post-call logging
        usage = response.usage or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        actual_cost = self.budget_guard.estimate_cost(model, input_tokens, output_tokens)
        
        # Post-call diagnostic analysis
        response_dict = {
            "usage": usage,
            "content": response.content,
            "stop_reason": response.stop_reason,
        }
        post_report = self.diagnostics.post_call_analysis(
            pre_report, response_dict, duration, estimated_cost
        )
        
        # Log the diagnostic report
        self.diagnostics.log_report(post_report)
        
        # Store report for API access
        self.diagnostic_reports.append(post_report)
        
        # Check for alerts
        self.alert_system.send_alert(post_report)
        
        # Log the call
        self.call_logger.log_call(
            operation=operation,
            model=model,
            provider=settings.llm_provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            message_chars=message_chars,
            tools_included=len(tools) > 0,
            tools_size_bytes=tools_size,
            max_tokens=max_tokens,
            cost_cents=actual_cost,
            usage_data=usage,
        )
        
        # Update session cost
        self.budget_guard.update_session_cost(actual_cost)

        # Process response, handling tool calls
        return await self._process_response(response, operation, context_messages)

    async def _process_response(
        self,
        response,
        operation: Optional[OperationType] = None,
        context_messages: Optional[list[dict]] = None
    ) -> str:
        """Process LLM response, handling any tool calls.
        
        Args:
            response: The LLM response
            operation: The operation type (defaults to tool_continuation for recursive calls)
            context_messages: The messages that were sent (for continuation calls)
        """
        # Default to tool_continuation for recursive calls
        if operation is None:
            operation = "tool_continuation"
            
        # Default to full message history if not provided
        if context_messages is None:
            context_messages = self.messages.copy()
            
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

            # Use continuation operation type
            continuation_operation: OperationType = "tool_continuation"
            model = self._get_model_for_operation(continuation_operation)
            max_tokens = self._get_max_tokens_for_operation(continuation_operation)
            system_prompt = self._get_system_prompt(continuation_operation)
            continuation_context = self._get_context_for_llm(continuation_operation)

            # Prepare for continuation call
            tools = self.registry.to_anthropic_tools()
            
            # Pre-call cost checks for continuation
            message_chars = calculate_message_chars(continuation_context)
            tools_size = calculate_tools_size(tools)
            system_chars = len(system_prompt)
            total_chars = message_chars + system_chars
            
            # Estimate tokens for continuation
            estimated_input_tokens = estimate_tokens_from_chars(total_chars + tools_size)
            estimated_output_tokens = max_tokens
            
            # Estimate cost
            estimated_cost = self.budget_guard.estimate_cost(
                model, estimated_input_tokens, estimated_output_tokens
            )
            
            # Check operation-specific budget for continuation
            allowed, error_msg = self.operation_budget_guard.check_operation_budget(
                continuation_operation, estimated_cost, estimated_input_tokens
            )
            if not allowed:
                return final_text + f"\n\n⚠️ Unable to continue: {error_msg}"
            
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
                max_tokens=max_tokens,
                system=system_prompt,
                tools=tools,
                messages=continuation_context,
            )
            
            # Post-call logging for continuation
            usage = continuation.usage or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            actual_cost = self.budget_guard.estimate_cost(model, input_tokens, output_tokens)
            
            # Log the continuation call
            self.call_logger.log_call(
                operation=continuation_operation,
                model=model,
                provider=settings.llm_provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                message_chars=message_chars,
                tools_included=len(tools) > 0,
                tools_size_bytes=tools_size,
                max_tokens=max_tokens,
                cost_cents=actual_cost,
                usage_data=usage,
            )
            
            # Update session cost
            self.budget_guard.update_session_cost(actual_cost)

            return await self._process_response(continuation, continuation_operation, continuation_context)

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
