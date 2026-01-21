"""LLM diagnostic and cost spike detection system."""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticReport:
    """Comprehensive report of LLM call diagnostics."""
    
    timestamp: str
    operation_type: str
    model_used: str
    model_expected: str
    model_validation: bool
    
    has_tools_schema: bool
    tools_schema_size: int
    
    system_prompt_size: int
    system_prompt_ok: bool
    
    history_message_count: int
    history_total_chars: int
    history_ok: bool
    
    sheet_content_size: int
    sheet_content_ok: bool
    
    max_tokens_requested: int
    max_tokens_ok: bool
    
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost: float = 0.0
    actual_cost: Optional[float] = None
    
    duration_ms: float = 0.0
    
    is_spike: bool = False
    warnings: List[str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        """Initialize lists if None."""
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json_log(self) -> dict:
        """Convert to structured log format."""
        return {
            "timestamp": self.timestamp,
            "operation": self.operation_type,
            "model": self.model_used,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost / 100.0,  # Convert cents to USD
            "actual_cost_usd": self.actual_cost / 100.0 if self.actual_cost else None,
            "is_spike": self.is_spike,
            "validation": {
                "model_ok": self.model_validation,
                "tools_ok": not self.has_tools_schema,
                "prompt_size_ok": self.system_prompt_ok,
                "history_ok": self.history_ok,
                "max_tokens_ok": self.max_tokens_ok,
            },
            "warnings": self.warnings,
        }


class CostSpikeDetector:
    """Detect abnormal cost patterns in LLM calls."""
    
    # Expected cost ranges by operation type (in cents)
    EXPECTED_COSTS = {
        "parser": 0.1,       # $0.001 = 0.1 cents
        "helper": 0.3,       # $0.003 = 0.3 cents
        "ai_assist": 1.0,    # $0.01 = 1 cent
        "planning": 5.0,     # $0.05 = 5 cents
        "full_agent": 5.0,   # $0.05 = 5 cents
        "tool_continuation": 2.0,  # $0.02 = 2 cents
    }
    
    def __init__(self, threshold_multiplier: float = 2.0):
        """Initialize the detector.
        
        Args:
            threshold_multiplier: Multiplier for expected cost to determine spike threshold
        """
        self.threshold_multiplier = threshold_multiplier
    
    def is_spike(self, actual_cost: float, operation_type: str) -> bool:
        """Determine if a cost is a spike for the operation type.
        
        Args:
            actual_cost: Actual cost in cents
            operation_type: Type of operation
            
        Returns:
            True if cost is abnormally high
        """
        threshold = self.calculate_threshold(operation_type)
        return actual_cost > threshold
    
    def calculate_threshold(self, operation_type: str) -> float:
        """Calculate spike threshold for operation type.
        
        Args:
            operation_type: Type of operation
            
        Returns:
            Threshold in cents
        """
        expected = self.EXPECTED_COSTS.get(operation_type, 1.0)
        return expected * self.threshold_multiplier


class LLMDiagnostics:
    """Diagnostic and monitoring system for LLM calls."""
    
    def __init__(
        self,
        max_system_prompt_chars: int = 500,
        max_history_messages: int = 10,
        max_sheet_content_chars: int = 5000,
        max_tools_schema_bytes: int = 0,
        spike_detector: Optional[CostSpikeDetector] = None,
    ):
        """Initialize diagnostics system.
        
        Args:
            max_system_prompt_chars: Maximum allowed system prompt size
            max_history_messages: Maximum allowed message history count
            max_sheet_content_chars: Maximum allowed sheet content size
            max_tools_schema_bytes: Maximum allowed tools schema size (0 = no tools)
            spike_detector: Cost spike detector instance
        """
        self.max_system_prompt_chars = max_system_prompt_chars
        self.max_history_messages = max_history_messages
        self.max_sheet_content_chars = max_sheet_content_chars
        self.max_tools_schema_bytes = max_tools_schema_bytes
        self.spike_detector = spike_detector or CostSpikeDetector()
    
    def pre_call_check(self, payload: dict, operation_type: str, expected_model: str) -> DiagnosticReport:
        """Perform pre-call validation checks.
        
        Args:
            payload: LLM API payload
            operation_type: Type of operation
            expected_model: Expected model to be used
            
        Returns:
            DiagnosticReport with pre-call validation results
        """
        warnings = []
        errors = []
        
        # Extract payload components
        model = payload.get("model", "")
        system = payload.get("system", "")
        messages = payload.get("messages", [])
        tools = payload.get("tools", [])
        max_tokens = payload.get("max_tokens", 0)
        
        # 1. Model validation
        model_validation = self._validate_model(model, expected_model, warnings)
        
        # 2. Tools schema check
        has_tools = len(tools) > 0
        tools_size = len(json.dumps(tools).encode("utf-8")) if has_tools else 0
        
        if has_tools:
            warnings.append(f"Tools schema present ({tools_size} bytes)")
        if tools_size > self.max_tools_schema_bytes:
            errors.append(
                f"Tools schema size ({tools_size} bytes) exceeds maximum "
                f"({self.max_tools_schema_bytes} bytes)"
            )
        
        # 3. System prompt size check
        system_size = len(system)
        system_ok = system_size <= self.max_system_prompt_chars
        
        if not system_ok:
            warnings.append(
                f"System prompt size ({system_size} chars) exceeds threshold "
                f"({self.max_system_prompt_chars} chars)"
            )
        
        # 4. Chat history check
        history_count = len(messages)
        history_chars = self._calculate_history_chars(messages)
        history_ok = history_count <= self.max_history_messages
        
        if not history_ok:
            warnings.append(
                f"Message history count ({history_count}) exceeds threshold "
                f"({self.max_history_messages})"
            )
        
        # 5. Sheet content detection
        sheet_content_size = self._detect_sheet_content(messages)
        sheet_ok = sheet_content_size <= self.max_sheet_content_chars
        
        if not sheet_ok:
            warnings.append(
                f"Sheet content size ({sheet_content_size} chars) exceeds threshold "
                f"({self.max_sheet_content_chars} chars)"
            )
        
        # 6. Max tokens validation
        max_tokens_ok = self._validate_max_tokens(max_tokens, operation_type, warnings)
        
        return DiagnosticReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            operation_type=operation_type,
            model_used=model,
            model_expected=expected_model,
            model_validation=model_validation,
            has_tools_schema=has_tools,
            tools_schema_size=tools_size,
            system_prompt_size=system_size,
            system_prompt_ok=system_ok,
            history_message_count=history_count,
            history_total_chars=history_chars,
            history_ok=history_ok,
            sheet_content_size=sheet_content_size,
            sheet_content_ok=sheet_ok,
            max_tokens_requested=max_tokens,
            max_tokens_ok=max_tokens_ok,
            warnings=warnings,
            errors=errors,
        )
    
    def post_call_analysis(
        self,
        pre_report: DiagnosticReport,
        response: dict,
        duration: float,
        estimated_cost: float,
    ) -> DiagnosticReport:
        """Perform post-call analysis with actual usage data.
        
        Args:
            pre_report: Pre-call diagnostic report
            response: LLM API response
            duration: Call duration in milliseconds
            estimated_cost: Estimated cost in cents
            
        Returns:
            Updated DiagnosticReport with post-call data
        """
        # Extract usage data from response
        usage = response.get("usage", {})
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
        
        # Extract actual cost if available (OpenRouter native_tokens_* fields)
        actual_cost = None
        if "usage" in response:
            # Check for OpenRouter cost data
            native_cost = usage.get("native_tokens_cost")
            if native_cost is not None:
                actual_cost = native_cost * 100  # Convert to cents
        
        # Update report with post-call data
        pre_report.input_tokens = input_tokens
        pre_report.output_tokens = output_tokens
        pre_report.estimated_cost = estimated_cost
        pre_report.actual_cost = actual_cost
        pre_report.duration_ms = duration
        
        # Detect cost spike
        cost_to_check = actual_cost if actual_cost is not None else estimated_cost
        pre_report.is_spike = self.spike_detector.is_spike(
            cost_to_check, pre_report.operation_type
        )
        
        if pre_report.is_spike:
            pre_report.warnings.append(
                f"Cost spike detected: {cost_to_check:.4f} cents for {pre_report.operation_type}"
            )
        
        # Compare estimated vs actual cost if available
        if actual_cost is not None:
            # Avoid division by zero, use the larger of the two costs
            denominator = max(actual_cost, estimated_cost, 0.0001)
            cost_difference_ratio = abs(actual_cost - estimated_cost) / denominator
            if cost_difference_ratio > 0.5:
                pre_report.warnings.append(
                    f"Cost estimate mismatch: estimated {estimated_cost:.4f} cents, "
                    f"actual {actual_cost:.4f} cents"
                )
        
        return pre_report
    
    def _validate_model(self, model: str, expected_model: str, warnings: List[str]) -> bool:
        """Validate model string.
        
        Args:
            model: Actual model being used
            expected_model: Expected model
            warnings: List to append warnings to
            
        Returns:
            True if model is valid
        """
        # Check if model matches expected
        if model != expected_model and expected_model:
            warnings.append(f"Model mismatch: using '{model}', expected '{expected_model}'")
            return False
        
        # Check for :free suffix when expected
        # This is a heuristic - if the config uses free models, we expect :free suffix
        # We'll validate this in actual integration
        
        return True
    
    def _calculate_history_chars(self, messages: list) -> int:
        """Calculate total character count in message history.
        
        Args:
            messages: List of messages
            
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
    
    def _detect_sheet_content(self, messages: list) -> int:
        """Detect and measure sheet content in messages.
        
        This is a heuristic to detect if structured spreadsheet data
        is being sent in messages. It looks for patterns that suggest
        spreadsheet-specific content rather than just words like "sheet".
        
        Args:
            messages: List of messages
            
        Returns:
            Estimated size of sheet content in characters
        """
        # More sophisticated heuristic: look for structured data patterns
        # and cell reference patterns, not just words
        sheet_content = 0
        
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                # Count content if it has multiple indicators of spreadsheet data:
                # - Cell references like A1, B2, etc.
                # - Multiple instances of "formula", "range", etc. in context
                # - Structured data patterns (multiple | or tab characters)
                indicators = 0
                
                # Check for cell references (e.g., A1, B2, C10)
                import re
                if re.search(r'\b[A-Z]+\d+\b', content):
                    indicators += 1
                
                # Check for formula syntax
                if '=' in content and any(func in content for func in ['SUM', 'AVERAGE', 'IF', 'VLOOKUP']):
                    indicators += 1
                
                # Check for structured data (tables with | or tabs)
                if content.count('|') > 5 or content.count('\t') > 5:
                    indicators += 1
                
                # Only count if we have multiple indicators
                if indicators >= 2:
                    sheet_content += len(content)
        
        return sheet_content
    
    def _validate_max_tokens(self, max_tokens: int, operation_type: str, warnings: List[str]) -> bool:
        """Validate max_tokens setting for operation type.
        
        Args:
            max_tokens: Requested max_tokens
            operation_type: Type of operation
            warnings: List to append warnings to
            
        Returns:
            True if max_tokens is appropriate
        """
        # Expected max_tokens by operation type
        expected_max_tokens = {
            "parser": 300,
            "helper": 400,
            "ai_assist": 400,
            "planning": 800,
            "full_agent": 4096,
            "tool_continuation": 600,
        }
        
        expected = expected_max_tokens.get(operation_type, 4096)
        
        if max_tokens > expected * 2:
            warnings.append(
                f"max_tokens ({max_tokens}) is high for {operation_type} "
                f"(expected ~{expected})"
            )
            return False
        
        return True
    
    def log_report(self, report: DiagnosticReport):
        """Log diagnostic report.
        
        Args:
            report: Diagnostic report to log
        """
        log_data = report.to_json_log()
        
        if report.is_spike or report.errors:
            logger.warning(f"LLM Diagnostic Alert: {json.dumps(log_data)}")
        else:
            logger.info(f"LLM Diagnostic: {json.dumps(log_data)}")


class DiagnosticAlertSystem:
    """Alert system for cost spikes and diagnostic issues."""
    
    def __init__(self, enabled: bool = True):
        """Initialize alert system.
        
        Args:
            enabled: Whether alerts are enabled
        """
        self.enabled = enabled
    
    def should_alert(self, report: DiagnosticReport) -> bool:
        """Determine if an alert should be sent.
        
        Args:
            report: Diagnostic report
            
        Returns:
            True if alert should be sent
        """
        if not self.enabled:
            return False
        
        # Alert on spikes
        if report.is_spike:
            return True
        
        # Alert on errors
        if report.errors:
            return True
        
        # Alert on multiple warnings
        if len(report.warnings) >= 3:
            return True
        
        return False
    
    def send_alert(self, report: DiagnosticReport):
        """Send alert for diagnostic report.
        
        Args:
            report: Diagnostic report
        """
        if not self.should_alert(report):
            return
        
        # For now, just log as warning
        # In production, this could send to webhook, email, etc.
        alert_msg = (
            f"⚠️ LLM COST ALERT ⚠️\n"
            f"Operation: {report.operation_type}\n"
            f"Model: {report.model_used}\n"
            f"Cost: {report.actual_cost or report.estimated_cost:.4f} cents\n"
            f"Is Spike: {report.is_spike}\n"
            f"Errors: {report.errors}\n"
            f"Warnings: {report.warnings}\n"
        )
        
        logger.warning(alert_msg)
