"""Tests for LLM cost tracking module."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock

from sheetsmith.llm.cost_tracking import (
    LLMCallLogger,
    BudgetGuard,
    LLMCallRecord,
    calculate_message_chars,
    calculate_tools_size,
    estimate_tokens_from_chars,
)


class TestLLMCallLogger:
    """Test LLM call logging functionality."""

    def test_logger_initialization(self, tmp_path):
        """Test logger can be initialized."""
        log_path = tmp_path / "test.jsonl"
        logger = LLMCallLogger(log_path=log_path, enabled=True)
        
        assert logger.log_path == log_path
        assert logger.enabled is True
        assert len(logger.session_calls) == 0
        assert log_path.parent.exists()

    def test_log_call_creates_record(self, tmp_path):
        """Test logging an LLM call creates a record."""
        log_path = tmp_path / "test.jsonl"
        logger = LLMCallLogger(log_path=log_path, enabled=True)
        
        record = logger.log_call(
            operation="test_operation",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            input_tokens=100,
            output_tokens=50,
            message_chars=500,
            tools_included=True,
            tools_size_bytes=1000,
            max_tokens=4096,
            cost_cents=0.045,
            usage_data={"input_tokens": 100, "output_tokens": 50},
        )
        
        assert record.operation == "test_operation"
        assert record.model == "claude-sonnet-4-20250514"
        assert record.provider == "anthropic"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.total_tokens == 150
        assert record.message_chars == 500
        assert record.tools_included is True
        assert record.tools_size_bytes == 1000
        assert record.max_tokens == 4096
        assert record.cost_cents == 0.045
        
        assert len(logger.session_calls) == 1

    def test_log_call_writes_to_file(self, tmp_path):
        """Test that log calls are written to file."""
        log_path = tmp_path / "test.jsonl"
        logger = LLMCallLogger(log_path=log_path, enabled=True)
        
        logger.log_call(
            operation="test",
            model="claude-3-haiku",
            provider="anthropic",
            input_tokens=10,
            output_tokens=5,
            message_chars=50,
            tools_included=False,
            tools_size_bytes=0,
            max_tokens=1024,
            cost_cents=0.001,
        )
        
        assert log_path.exists()
        
        with open(log_path) as f:
            lines = f.readlines()
        
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["operation"] == "test"
        assert data["model"] == "claude-3-haiku"
        assert data["input_tokens"] == 10

    def test_log_disabled(self, tmp_path):
        """Test that logging can be disabled."""
        log_path = tmp_path / "test.jsonl"
        logger = LLMCallLogger(log_path=log_path, enabled=False)
        
        logger.log_call(
            operation="test",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            input_tokens=10,
            output_tokens=5,
            message_chars=50,
            tools_included=False,
            tools_size_bytes=0,
            max_tokens=1024,
            cost_cents=0.001,
        )
        
        assert len(logger.session_calls) == 1
        assert not log_path.exists()  # File should not be created

    def test_get_session_summary(self, tmp_path):
        """Test getting session summary."""
        log_path = tmp_path / "test.jsonl"
        logger = LLMCallLogger(log_path=log_path, enabled=True)
        
        # Log multiple calls
        logger.log_call(
            operation="call1",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            input_tokens=100,
            output_tokens=50,
            message_chars=500,
            tools_included=True,
            tools_size_bytes=1000,
            max_tokens=4096,
            cost_cents=0.045,
        )
        
        logger.log_call(
            operation="call2",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            input_tokens=200,
            output_tokens=100,
            message_chars=1000,
            tools_included=False,
            tools_size_bytes=0,
            max_tokens=4096,
            cost_cents=0.09,
        )
        
        summary = logger.get_session_summary()
        
        assert summary["total_calls"] == 2
        assert summary["total_cost_cents"] == 0.135
        assert summary["total_input_tokens"] == 300
        assert summary["total_output_tokens"] == 150
        assert summary["total_tokens"] == 450
        assert summary["last_call"]["operation"] == "call2"

    def test_get_session_summary_empty(self, tmp_path):
        """Test getting session summary when empty."""
        log_path = tmp_path / "test.jsonl"
        logger = LLMCallLogger(log_path=log_path, enabled=True)
        
        summary = logger.get_session_summary()
        
        assert summary["total_calls"] == 0
        assert summary["total_cost_cents"] == 0.0
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0

    def test_get_recent_calls(self, tmp_path):
        """Test getting recent calls."""
        log_path = tmp_path / "test.jsonl"
        logger = LLMCallLogger(log_path=log_path, enabled=True)
        
        # Log 15 calls
        for i in range(15):
            logger.log_call(
                operation=f"call{i}",
                model="claude-sonnet-4-20250514",
                provider="anthropic",
                input_tokens=10 * i,
                output_tokens=5 * i,
                message_chars=50 * i,
                tools_included=False,
                tools_size_bytes=0,
                max_tokens=1024,
                cost_cents=0.001 * i,
            )
        
        recent = logger.get_recent_calls(limit=10)
        
        assert len(recent) == 10
        assert recent[0]["operation"] == "call5"  # Last 10 calls
        assert recent[-1]["operation"] == "call14"

    def test_reset_session(self, tmp_path):
        """Test resetting session."""
        log_path = tmp_path / "test.jsonl"
        logger = LLMCallLogger(log_path=log_path, enabled=True)
        
        logger.log_call(
            operation="test",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            input_tokens=100,
            output_tokens=50,
            message_chars=500,
            tools_included=False,
            tools_size_bytes=0,
            max_tokens=4096,
            cost_cents=0.045,
        )
        
        assert len(logger.session_calls) == 1
        
        logger.reset_session()
        
        assert len(logger.session_calls) == 0


class TestBudgetGuard:
    """Test budget guard functionality."""

    def test_budget_guard_initialization(self):
        """Test budget guard can be initialized."""
        guard = BudgetGuard(
            payload_max_chars=50000,
            max_input_tokens=100000,
            per_request_budget_cents=5.0,
            session_budget_cents=50.0,
            alert_threshold_cents=1.0,
        )
        
        assert guard.payload_max_chars == 50000
        assert guard.max_input_tokens == 100000
        assert guard.per_request_budget_cents == 5.0
        assert guard.session_budget_cents == 50.0
        assert guard.alert_threshold_cents == 1.0
        assert guard.session_cost_cents == 0.0

    def test_estimate_cost_sonnet(self):
        """Test cost estimation for Claude Sonnet."""
        guard = BudgetGuard()
        
        # $3 per million input, $15 per million output
        cost = guard.estimate_cost(
            model="claude-sonnet-4-20250514",
            input_tokens=1000,
            output_tokens=500,
        )
        
        # (1000/1M * 300 cents) + (500/1M * 1500 cents) = 0.3 + 0.75 = 1.05 cents
        assert cost == pytest.approx(1.05, rel=0.01)

    def test_estimate_cost_haiku(self):
        """Test cost estimation for Claude Haiku."""
        guard = BudgetGuard()
        
        # $0.25 per million input, $1.25 per million output
        cost = guard.estimate_cost(
            model="claude-3-haiku",
            input_tokens=1000,
            output_tokens=500,
        )
        
        # (1000/1M * 25 cents) + (500/1M * 125 cents) = 0.025 + 0.0625 = 0.0875 cents
        assert cost == pytest.approx(0.0875, rel=0.01)

    def test_check_payload_size_within_limit(self):
        """Test payload size check passes when within limit."""
        guard = BudgetGuard(payload_max_chars=1000)
        
        # Should not raise
        guard.check_payload_size(500)

    def test_check_payload_size_exceeds_limit(self):
        """Test payload size check fails when exceeding limit."""
        guard = BudgetGuard(payload_max_chars=1000)
        
        with pytest.raises(ValueError, match="Payload size.*exceeds maximum"):
            guard.check_payload_size(1500)

    def test_check_token_limit_within_limit(self):
        """Test token limit check passes when within limit."""
        guard = BudgetGuard(max_input_tokens=10000)
        
        # Should not raise
        guard.check_token_limit(5000)

    def test_check_token_limit_exceeds_limit(self):
        """Test token limit check fails when exceeding limit."""
        guard = BudgetGuard(max_input_tokens=10000)
        
        with pytest.raises(ValueError, match="Estimated input tokens.*exceeds maximum"):
            guard.check_token_limit(15000)

    def test_check_budget_per_request_exceeded(self):
        """Test budget check when per-request budget exceeded."""
        guard = BudgetGuard(per_request_budget_cents=1.0)
        
        # High token counts that will exceed budget
        allowed, message = guard.check_budget(
            model="claude-sonnet-4-20250514",
            estimated_input_tokens=10000,  # Will cost > 1 cent
            estimated_output_tokens=10000,
        )
        
        assert allowed is False
        assert "per-request budget" in message.lower()

    def test_check_budget_session_exceeded(self):
        """Test budget check when session budget exceeded."""
        guard = BudgetGuard(
            per_request_budget_cents=5.0,
            session_budget_cents=10.0,
        )
        
        # Set session cost high
        guard.session_cost_cents = 9.5
        
        # Request that would push over session budget
        allowed, message = guard.check_budget(
            model="claude-sonnet-4-20250514",
            estimated_input_tokens=1000,
            estimated_output_tokens=500,
        )
        
        assert allowed is False
        assert "session budget" in message.lower()

    def test_check_budget_alert_threshold(self):
        """Test budget check triggers alert at threshold."""
        guard = BudgetGuard(
            per_request_budget_cents=5.0,
            session_budget_cents=50.0,
            alert_threshold_cents=1.0,
        )
        
        # Request that exceeds alert threshold but within budget
        allowed, message = guard.check_budget(
            model="claude-sonnet-4-20250514",
            estimated_input_tokens=1000,
            estimated_output_tokens=500,
        )
        
        assert allowed is True
        assert "high cost alert" in message.lower()

    def test_check_budget_within_all_limits(self):
        """Test budget check passes when within all limits."""
        guard = BudgetGuard(
            per_request_budget_cents=5.0,
            session_budget_cents=50.0,
            alert_threshold_cents=1.0,
        )
        
        # Small request well within limits
        allowed, message = guard.check_budget(
            model="claude-3-haiku",
            estimated_input_tokens=100,
            estimated_output_tokens=50,
        )
        
        assert allowed is True
        assert message == ""

    def test_update_session_cost(self):
        """Test updating session cost."""
        guard = BudgetGuard()
        
        assert guard.session_cost_cents == 0.0
        
        guard.update_session_cost(1.5)
        assert guard.session_cost_cents == 1.5
        
        guard.update_session_cost(0.5)
        assert guard.session_cost_cents == 2.0

    def test_get_budget_status(self):
        """Test getting budget status."""
        guard = BudgetGuard(
            per_request_budget_cents=5.0,
            session_budget_cents=50.0,
        )
        
        guard.session_cost_cents = 25.0
        
        status = guard.get_budget_status()
        
        assert status["session_cost_cents"] == 25.0
        assert status["session_budget_cents"] == 50.0
        assert status["remaining_budget_cents"] == 25.0
        assert status["budget_used_percent"] == 50.0
        assert status["per_request_budget_cents"] == 5.0

    def test_reset_session(self):
        """Test resetting session."""
        guard = BudgetGuard()
        
        guard.session_cost_cents = 10.0
        assert guard.session_cost_cents == 10.0
        
        guard.reset_session()
        assert guard.session_cost_cents == 0.0


class TestHelperFunctions:
    """Test helper functions."""

    def test_calculate_message_chars_simple(self):
        """Test calculating message characters with simple messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        
        chars = calculate_message_chars(messages)
        assert chars == len("Hello") + len("Hi there")

    def test_calculate_message_chars_complex(self):
        """Test calculating message characters with complex content."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "tool_result", "content": "Result data"},
                ],
            },
        ]
        
        chars = calculate_message_chars(messages)
        assert chars == len("Hello") + len("Result data")

    def test_calculate_message_chars_empty(self):
        """Test calculating message characters with empty messages."""
        messages = []
        
        chars = calculate_message_chars(messages)
        assert chars == 0

    def test_calculate_tools_size(self):
        """Test calculating tools size."""
        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
        
        size = calculate_tools_size(tools)
        assert size > 0
        assert size == len(json.dumps(tools).encode("utf-8"))

    def test_calculate_tools_size_empty(self):
        """Test calculating tools size with empty list."""
        size = calculate_tools_size([])
        assert size == 0

    def test_estimate_tokens_from_chars(self):
        """Test estimating tokens from characters."""
        # Should be roughly chars/4 + 100
        tokens = estimate_tokens_from_chars(400)
        assert tokens == 200  # 400/4 + 100 = 200
        
        tokens = estimate_tokens_from_chars(1000)
        assert tokens == 350  # 1000/4 + 100 = 350
