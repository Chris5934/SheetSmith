"""Integration tests for LLM diagnostics wrapper."""

import pytest
from unittest.mock import Mock, MagicMock

from sheetsmith.llm.base import LLMResponse
from sheetsmith.llm.diagnostics import LLMDiagnostics, DiagnosticAlertSystem
from sheetsmith.llm.diagnostic_wrapper import (
    call_llm_with_diagnostics_sync,
    LLMCallBlockedError,
)
from sheetsmith.llm.cost_tracking import BudgetGuard


class TestDiagnosticWrapper:
    """Test diagnostic wrapper integration."""
    
    def test_successful_llm_call_with_diagnostics(self):
        """Test successful LLM call with diagnostics."""
        # Mock LLM client
        mock_client = Mock()
        mock_response = LLMResponse(
            content=[{"type": "text", "text": "Hello"}],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        mock_client.create_message.return_value = mock_response
        
        # Set up diagnostics
        diagnostics = LLMDiagnostics()
        
        # Make call
        response, report = call_llm_with_diagnostics_sync(
            client=mock_client,
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful",
            tools=[],
            max_tokens=300,
            model="claude-3-haiku",
            operation_type="parser",
            expected_model="claude-3-haiku",
            diagnostics=diagnostics,
        )
        
        # Verify call was made
        assert mock_client.create_message.called
        
        # Verify response
        assert response == mock_response
        
        # Verify report
        assert report.operation_type == "parser"
        assert report.model_used == "claude-3-haiku"
        assert report.input_tokens == 100
        assert report.output_tokens == 50
        assert len(report.errors) == 0
    
    def test_blocked_call_with_tools(self):
        """Test LLM call blocked when tools present."""
        # Mock LLM client
        mock_client = Mock()
        
        # Set up diagnostics with no tools allowed
        diagnostics = LLMDiagnostics(max_tools_schema_bytes=0)
        
        # Try to make call with tools
        with pytest.raises(LLMCallBlockedError) as exc_info:
            call_llm_with_diagnostics_sync(
                client=mock_client,
                messages=[{"role": "user", "content": "Hello"}],
                system="You are helpful",
                tools=[{"name": "test_tool", "description": "A test"}],
                max_tokens=300,
                model="claude-3-haiku",
                operation_type="parser",
                expected_model="claude-3-haiku",
                diagnostics=diagnostics,
            )
        
        # Verify error message
        assert "Tools schema size" in str(exc_info.value)
        
        # Verify LLM was not called
        assert not mock_client.create_message.called
    
    def test_cost_spike_detection(self):
        """Test cost spike detection in wrapper."""
        # Mock LLM client with very high token usage for Sonnet (expensive model)
        mock_client = Mock()
        mock_response = LLMResponse(
            content=[{"type": "text", "text": "Hello"}],
            stop_reason="end_turn",
            usage={"input_tokens": 100000, "output_tokens": 50000},
        )
        mock_client.create_message.return_value = mock_response
        
        # Set up diagnostics and budget guard for cost estimation
        diagnostics = LLMDiagnostics()
        alert_system = DiagnosticAlertSystem(enabled=True)
        budget_guard = BudgetGuard()
        
        # Make call with expensive model
        response, report = call_llm_with_diagnostics_sync(
            client=mock_client,
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful",
            tools=[],
            max_tokens=300,
            model="claude-sonnet-4-20250514",
            operation_type="parser",
            expected_model="claude-sonnet-4-20250514",
            diagnostics=diagnostics,
            budget_guard=budget_guard,
            alert_system=alert_system,
        )
        
        # Verify spike was detected
        # Parser expected cost is 0.1 cents, with threshold multiplier of 2.0 = 0.2 cents
        # Estimated cost is based on estimated input tokens + max_tokens output
        # The actual cost calculation will be higher with real usage
        assert report.estimated_cost > 0.2  # Above threshold for parser
        assert report.is_spike is True
        assert any("Cost spike" in w for w in report.warnings)
    
    def test_diagnostic_with_budget_guard(self):
        """Test diagnostic wrapper with budget guard."""
        # Mock LLM client
        mock_client = Mock()
        mock_response = LLMResponse(
            content=[{"type": "text", "text": "Hello"}],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        mock_client.create_message.return_value = mock_response
        
        # Set up diagnostics and budget guard
        diagnostics = LLMDiagnostics()
        budget_guard = BudgetGuard(
            per_request_budget_cents=10.0,
            session_budget_cents=50.0,
        )
        
        # Make call
        response, report = call_llm_with_diagnostics_sync(
            client=mock_client,
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful",
            tools=[],
            max_tokens=300,
            model="claude-3-haiku",
            operation_type="parser",
            expected_model="claude-3-haiku",
            diagnostics=diagnostics,
            budget_guard=budget_guard,
        )
        
        # Verify estimated cost was calculated
        assert report.estimated_cost > 0
    
    def test_warnings_logged_for_issues(self):
        """Test that warnings are logged for various issues."""
        # Mock LLM client
        mock_client = Mock()
        mock_response = LLMResponse(
            content=[{"type": "text", "text": "Hello"}],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        mock_client.create_message.return_value = mock_response
        
        # Set up diagnostics with strict limits
        diagnostics = LLMDiagnostics(
            max_system_prompt_chars=10,
            max_history_messages=1,
        )
        
        # Make call with issues
        response, report = call_llm_with_diagnostics_sync(
            client=mock_client,
            messages=[
                {"role": "user", "content": "Message 1"},
                {"role": "assistant", "content": "Response 1"},
                {"role": "user", "content": "Message 2"},
            ],
            system="This is a longer system prompt",
            tools=[],
            max_tokens=300,
            model="claude-3-haiku",
            operation_type="parser",
            expected_model="claude-3-haiku",
            diagnostics=diagnostics,
        )
        
        # Verify warnings were generated
        assert len(report.warnings) > 0
        assert any("System prompt size" in w for w in report.warnings)
        assert any("Message history count" in w for w in report.warnings)
    
    def test_model_mismatch_warning(self):
        """Test warning when model doesn't match expected."""
        # Mock LLM client
        mock_client = Mock()
        mock_response = LLMResponse(
            content=[{"type": "text", "text": "Hello"}],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        mock_client.create_message.return_value = mock_response
        
        # Set up diagnostics
        diagnostics = LLMDiagnostics()
        
        # Make call with model mismatch
        response, report = call_llm_with_diagnostics_sync(
            client=mock_client,
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful",
            tools=[],
            max_tokens=300,
            model="claude-3-opus",
            operation_type="parser",
            expected_model="claude-3-haiku",
            diagnostics=diagnostics,
        )
        
        # Verify model mismatch warning
        assert report.model_validation is False
        assert any("Model mismatch" in w for w in report.warnings)
