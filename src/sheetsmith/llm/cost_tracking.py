"""LLM cost tracking and budget management."""

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class LLMCallRecord:
    """Record of a single LLM API call."""
    
    timestamp: str
    operation: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    message_chars: int
    tools_included: bool
    tools_size_bytes: int
    max_tokens: int
    cost_cents: float
    usage_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class LLMCallLogger:
    """Logger for tracking LLM API calls and costs."""
    
    def __init__(self, log_path: Path, enabled: bool = True):
        """Initialize the logger.
        
        Args:
            log_path: Path to the JSONL log file
            enabled: Whether logging is enabled
        """
        self.log_path = log_path
        self.enabled = enabled
        self.session_calls: list[LLMCallRecord] = []
        
        # Ensure log directory exists
        if self.enabled:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log_call(
        self,
        operation: str,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        message_chars: int,
        tools_included: bool,
        tools_size_bytes: int,
        max_tokens: int,
        cost_cents: float,
        usage_data: Optional[Dict[str, Any]] = None,
    ) -> LLMCallRecord:
        """Log an LLM API call.
        
        Args:
            operation: Description of the operation (e.g., "process_message", "tool_continuation")
            model: Model name used
            provider: Provider name (e.g., "anthropic", "openrouter")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            message_chars: Total character count in messages
            tools_included: Whether tools JSON was included
            tools_size_bytes: Size of tools JSON in bytes
            max_tokens: max_tokens setting used
            cost_cents: Estimated or actual cost in cents
            usage_data: Optional raw usage data from the API
            
        Returns:
            The created LLMCallRecord
        """
        record = LLMCallRecord(
            timestamp=datetime.utcnow().isoformat(),
            operation=operation,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            message_chars=message_chars,
            tools_included=tools_included,
            tools_size_bytes=tools_size_bytes,
            max_tokens=max_tokens,
            cost_cents=cost_cents,
            usage_data=usage_data,
        )
        
        self.session_calls.append(record)
        
        if self.enabled:
            self._write_to_log(record)
        
        return record
    
    def _write_to_log(self, record: LLMCallRecord):
        """Write a record to the log file."""
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        except Exception as e:
            # Don't fail the application if logging fails
            print(f"Warning: Failed to write to cost log: {e}")
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the current session.
        
        Returns:
            Dictionary with session cost summary
        """
        if not self.session_calls:
            return {
                "total_calls": 0,
                "total_cost_cents": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
            }
        
        return {
            "total_calls": len(self.session_calls),
            "total_cost_cents": sum(call.cost_cents for call in self.session_calls),
            "total_input_tokens": sum(call.input_tokens for call in self.session_calls),
            "total_output_tokens": sum(call.output_tokens for call in self.session_calls),
            "total_tokens": sum(call.total_tokens for call in self.session_calls),
            "last_call": self.session_calls[-1].to_dict() if self.session_calls else None,
        }
    
    def get_recent_calls(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Get recent call records.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of recent call records as dictionaries
        """
        recent = self.session_calls[-limit:]
        return [call.to_dict() for call in recent]
    
    def reset_session(self):
        """Reset session tracking."""
        self.session_calls = []


class BudgetGuard:
    """Guards against excessive LLM costs with hard limits."""
    
    # Cost estimates per million tokens (in cents)
    COST_PER_MILLION_INPUT = {
        "claude-sonnet-4-20250514": 300,  # $3.00 per million input tokens
        "claude-3.5-sonnet": 300,
        "claude-3-opus": 1500,  # $15.00 per million
        "claude-3-sonnet": 300,
        "claude-3-haiku": 25,  # $0.25 per million
        "anthropic/claude-3.5-sonnet": 300,
        "anthropic/claude-3-opus": 1500,
    }
    
    COST_PER_MILLION_OUTPUT = {
        "claude-sonnet-4-20250514": 1500,  # $15.00 per million output tokens
        "claude-3.5-sonnet": 1500,
        "claude-3-opus": 7500,  # $75.00 per million
        "claude-3-sonnet": 1500,
        "claude-3-haiku": 125,  # $1.25 per million
        "anthropic/claude-3.5-sonnet": 1500,
        "anthropic/claude-3-opus": 7500,
    }
    
    def __init__(
        self,
        payload_max_chars: int = 50000,
        max_input_tokens: int = 100000,
        per_request_budget_cents: float = 5.0,
        session_budget_cents: float = 50.0,
        alert_threshold_cents: float = 1.0,
    ):
        """Initialize the budget guard.
        
        Args:
            payload_max_chars: Maximum characters allowed in message payload
            max_input_tokens: Maximum input tokens allowed per request
            per_request_budget_cents: Maximum cost per request in cents
            session_budget_cents: Maximum cost per session in cents
            alert_threshold_cents: Cost threshold for alerts in cents
        """
        self.payload_max_chars = payload_max_chars
        self.max_input_tokens = max_input_tokens
        self.per_request_budget_cents = per_request_budget_cents
        self.session_budget_cents = session_budget_cents
        self.alert_threshold_cents = alert_threshold_cents
        self.session_cost_cents = 0.0
    
    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate the cost of an LLM call in cents.
        
        Args:
            model: Model name
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens
            
        Returns:
            Estimated cost in cents
        """
        # Default to Sonnet pricing if model not found
        input_cost_per_m = self.COST_PER_MILLION_INPUT.get(
            model, self.COST_PER_MILLION_INPUT["claude-sonnet-4-20250514"]
        )
        output_cost_per_m = self.COST_PER_MILLION_OUTPUT.get(
            model, self.COST_PER_MILLION_OUTPUT["claude-sonnet-4-20250514"]
        )
        
        input_cost = (input_tokens / 1_000_000) * input_cost_per_m
        output_cost = (output_tokens / 1_000_000) * output_cost_per_m
        
        return input_cost + output_cost
    
    def check_payload_size(self, message_chars: int):
        """Check if payload size is within limits.
        
        Args:
            message_chars: Total character count in messages
            
        Raises:
            ValueError: If payload exceeds limits
        """
        if message_chars > self.payload_max_chars:
            raise ValueError(
                f"Payload size ({message_chars} chars) exceeds maximum "
                f"allowed ({self.payload_max_chars} chars). "
                f"Please reduce the message size or context."
            )
    
    def check_token_limit(self, estimated_input_tokens: int):
        """Check if estimated tokens are within limits.
        
        Args:
            estimated_input_tokens: Estimated input token count
            
        Raises:
            ValueError: If tokens exceed limits
        """
        if estimated_input_tokens > self.max_input_tokens:
            raise ValueError(
                f"Estimated input tokens ({estimated_input_tokens}) exceeds maximum "
                f"allowed ({self.max_input_tokens}). "
                f"Please reduce the context or message size."
            )
    
    def check_budget(
        self,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> tuple[bool, str]:
        """Check if the request is within budget.
        
        Args:
            model: Model name
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
            
        Returns:
            Tuple of (allowed, message)
        """
        estimated_cost = self.estimate_cost(model, estimated_input_tokens, estimated_output_tokens)
        
        # Check per-request budget
        if estimated_cost > self.per_request_budget_cents:
            return False, (
                f"Estimated cost ({estimated_cost:.4f} cents) exceeds per-request "
                f"budget ({self.per_request_budget_cents} cents). "
                f"Consider reducing max_tokens or context size."
            )
        
        # Check session budget
        if self.session_cost_cents + estimated_cost > self.session_budget_cents:
            return False, (
                f"Request would exceed session budget. "
                f"Current session cost: {self.session_cost_cents:.4f} cents, "
                f"estimated request cost: {estimated_cost:.4f} cents, "
                f"session budget: {self.session_budget_cents} cents. "
                f"Please reset the session or reduce request size."
            )
        
        # Check if alert threshold exceeded
        if estimated_cost > self.alert_threshold_cents:
            return True, (
                f"⚠️ High cost alert: This request is estimated to cost "
                f"{estimated_cost:.4f} cents (threshold: {self.alert_threshold_cents} cents)"
            )
        
        return True, ""
    
    def update_session_cost(self, actual_cost_cents: float):
        """Update the cumulative session cost.
        
        Args:
            actual_cost_cents: Actual cost of the request in cents
        """
        self.session_cost_cents += actual_cost_cents
    
    def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status.
        
        Returns:
            Dictionary with budget information
        """
        return {
            "session_cost_cents": self.session_cost_cents,
            "session_budget_cents": self.session_budget_cents,
            "remaining_budget_cents": self.session_budget_cents - self.session_cost_cents,
            "budget_used_percent": (
                (self.session_cost_cents / self.session_budget_cents) * 100
                if self.session_budget_cents > 0
                else 0
            ),
            "per_request_budget_cents": self.per_request_budget_cents,
        }
    
    def reset_session(self):
        """Reset session cost tracking."""
        self.session_cost_cents = 0.0


def calculate_message_chars(messages: list[dict]) -> int:
    """Calculate total character count in messages.
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        Total character count
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        total += len(item.get("text", ""))
                    elif item.get("type") == "tool_result":
                        total += len(str(item.get("content", "")))
    return total


def calculate_tools_size(tools: list[dict]) -> int:
    """Calculate size of tools JSON in bytes.
    
    Args:
        tools: List of tool definitions
        
    Returns:
        Size in bytes
    """
    if not tools:
        return 0
    return len(json.dumps(tools).encode("utf-8"))


def estimate_tokens_from_chars(chars: int) -> int:
    """Estimate token count from character count.
    
    Uses a rough estimate of 4 characters per token (conservative).
    
    Args:
        chars: Character count
        
    Returns:
        Estimated token count
    """
    return int(chars / 4) + 100  # Add buffer for safety
