"""Wrapper for LLM calls with diagnostic monitoring."""

import time
from typing import Optional, Tuple
from .base import LLMClient, LLMResponse
from .diagnostics import LLMDiagnostics, DiagnosticReport, DiagnosticAlertSystem
from .cost_tracking import BudgetGuard


class LLMCallBlockedError(Exception):
    """Exception raised when an LLM call is blocked by diagnostics."""
    
    def __init__(self, report: DiagnosticReport):
        self.report = report
        error_msg = f"LLM call blocked: {', '.join(report.errors)}"
        super().__init__(error_msg)


async def call_llm_with_diagnostics(
    client: LLMClient,
    messages: list[dict],
    system: str,
    tools: list[dict],
    max_tokens: int,
    model: str,
    operation_type: str,
    expected_model: str,
    diagnostics: LLMDiagnostics,
    budget_guard: Optional[BudgetGuard] = None,
    alert_system: Optional[DiagnosticAlertSystem] = None,
) -> Tuple[LLMResponse, DiagnosticReport]:
    """Call LLM with full diagnostic monitoring.
    
    Args:
        client: LLM client instance
        messages: List of messages
        system: System prompt
        tools: List of tool definitions
        max_tokens: Maximum tokens to generate
        model: Model to use
        operation_type: Type of operation
        expected_model: Expected model name
        diagnostics: Diagnostics instance
        budget_guard: Optional budget guard for cost checking
        alert_system: Optional alert system
        
    Returns:
        Tuple of (LLMResponse, DiagnosticReport)
        
    Raises:
        LLMCallBlockedError: If pre-call validation fails
    """
    # Build payload for diagnostics
    payload = {
        "model": model,
        "system": system,
        "messages": messages,
        "tools": tools,
        "max_tokens": max_tokens,
    }
    
    # Pre-call validation
    pre_report = diagnostics.pre_call_check(payload, operation_type, expected_model)
    
    # Block call if there are errors
    if pre_report.errors:
        raise LLMCallBlockedError(pre_report)
    
    # Estimate cost for budget checking
    if budget_guard:
        from .cost_tracking import estimate_tokens_from_chars, calculate_message_chars
        
        message_chars = calculate_message_chars(messages) + len(system)
        estimated_input_tokens = estimate_tokens_from_chars(message_chars)
        estimated_output_tokens = max_tokens
        estimated_cost = budget_guard.estimate_cost(
            model, estimated_input_tokens, estimated_output_tokens
        )
    else:
        estimated_cost = 0.0
    
    # Make the call
    start = time.time()
    response = client.create_message(
        messages=messages,
        system=system,
        tools=tools,
        max_tokens=max_tokens,
        model=model,
    )
    duration = (time.time() - start) * 1000  # Convert to milliseconds
    
    # Convert LLMResponse to dict for diagnostics
    response_dict = {
        "usage": response.usage or {},
        "content": response.content,
        "stop_reason": response.stop_reason,
    }
    
    # Post-call analysis
    post_report = diagnostics.post_call_analysis(
        pre_report, response_dict, duration, estimated_cost
    )
    
    # Log the report
    diagnostics.log_report(post_report)
    
    # Check for alerts
    if alert_system:
        alert_system.send_alert(post_report)
    
    return response, post_report


def call_llm_with_diagnostics_sync(
    client: LLMClient,
    messages: list[dict],
    system: str,
    tools: list[dict],
    max_tokens: int,
    model: str,
    operation_type: str,
    expected_model: str,
    diagnostics: LLMDiagnostics,
    budget_guard: Optional[BudgetGuard] = None,
    alert_system: Optional[DiagnosticAlertSystem] = None,
) -> Tuple[LLMResponse, DiagnosticReport]:
    """Synchronous version of call_llm_with_diagnostics.
    
    Args:
        client: LLM client instance
        messages: List of messages
        system: System prompt
        tools: List of tool definitions
        max_tokens: Maximum tokens to generate
        model: Model to use
        operation_type: Type of operation
        expected_model: Expected model name
        diagnostics: Diagnostics instance
        budget_guard: Optional budget guard for cost checking
        alert_system: Optional alert system
        
    Returns:
        Tuple of (LLMResponse, DiagnosticReport)
        
    Raises:
        LLMCallBlockedError: If pre-call validation fails
    """
    # Build payload for diagnostics
    payload = {
        "model": model,
        "system": system,
        "messages": messages,
        "tools": tools,
        "max_tokens": max_tokens,
    }
    
    # Pre-call validation
    pre_report = diagnostics.pre_call_check(payload, operation_type, expected_model)
    
    # Block call if there are errors
    if pre_report.errors:
        raise LLMCallBlockedError(pre_report)
    
    # Estimate cost for budget checking
    if budget_guard:
        from .cost_tracking import estimate_tokens_from_chars, calculate_message_chars
        
        message_chars = calculate_message_chars(messages) + len(system)
        estimated_input_tokens = estimate_tokens_from_chars(message_chars)
        estimated_output_tokens = max_tokens
        estimated_cost = budget_guard.estimate_cost(
            model, estimated_input_tokens, estimated_output_tokens
        )
    else:
        estimated_cost = 0.0
    
    # Make the call
    start = time.time()
    response = client.create_message(
        messages=messages,
        system=system,
        tools=tools,
        max_tokens=max_tokens,
        model=model,
    )
    duration = (time.time() - start) * 1000  # Convert to milliseconds
    
    # Convert LLMResponse to dict for diagnostics
    response_dict = {
        "usage": response.usage or {},
        "content": response.content,
        "stop_reason": response.stop_reason,
    }
    
    # Post-call analysis
    post_report = diagnostics.post_call_analysis(
        pre_report, response_dict, duration, estimated_cost
    )
    
    # Log the report
    diagnostics.log_report(post_report)
    
    # Check for alerts
    if alert_system:
        alert_system.send_alert(post_report)
    
    return response, post_report
