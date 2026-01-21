"""Tests for LLM budget and minimal prompts."""

import pytest

from sheetsmith.llm.budget import OperationBudgetGuard, OperationType
from sheetsmith.llm.minimal_prompts import (
    PARSER_SYSTEM_PROMPT,
    AI_ASSIST_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
)


class TestOperationBudgetGuard:
    """Test operation budget guard."""

    def test_get_budget_limit(self):
        """Test getting budget limits for operations."""
        guard = OperationBudgetGuard()
        
        assert guard.get_budget_limit("parser") == 0.001
        assert guard.get_budget_limit("ai_assist") == 0.01
        assert guard.get_budget_limit("planning") == 0.05
        assert guard.get_budget_limit("tool_continuation") == 0.02

    def test_get_token_limit(self):
        """Test getting token limits for operations."""
        guard = OperationBudgetGuard()
        
        assert guard.get_token_limit("parser") == 500
        assert guard.get_token_limit("ai_assist") == 1000
        assert guard.get_token_limit("planning") == 5000
        assert guard.get_token_limit("tool_continuation") == 3000

    def test_get_output_token_limit(self):
        """Test getting output token limits for operations."""
        guard = OperationBudgetGuard()
        
        assert guard.get_output_token_limit("parser") == 300
        assert guard.get_output_token_limit("ai_assist") == 400
        assert guard.get_output_token_limit("planning") == 800
        assert guard.get_output_token_limit("tool_continuation") == 600

    def test_check_operation_budget_within_limits(self):
        """Test operation within budget limits."""
        guard = OperationBudgetGuard()
        
        # Parser operation well within limits
        allowed, error = guard.check_operation_budget("parser", 0.0005, 100)
        assert allowed is True
        assert error is None

    def test_check_operation_budget_exceeds_cost(self):
        """Test operation exceeding cost budget."""
        guard = OperationBudgetGuard()
        
        # Parser operation exceeding cost budget
        allowed, error = guard.check_operation_budget("parser", 0.002, 100)
        assert allowed is False
        assert "exceeds budget" in error

    def test_check_operation_budget_exceeds_tokens(self):
        """Test operation exceeding token limit."""
        guard = OperationBudgetGuard()
        
        # Parser operation exceeding token limit
        allowed, error = guard.check_operation_budget("parser", 0.0005, 1000)
        assert allowed is False
        assert "exceeds token limit" in error


class TestMinimalPrompts:
    """Test minimal system prompts."""

    def test_parser_prompt_is_minimal(self):
        """Test parser prompt is concise."""
        # Should be under 500 chars
        assert len(PARSER_SYSTEM_PROMPT) < 500
        assert "JSON" in PARSER_SYSTEM_PROMPT
        assert "operation" in PARSER_SYSTEM_PROMPT

    def test_ai_assist_prompt_is_minimal(self):
        """Test AI assist prompt is concise."""
        # Should be under 500 chars
        assert len(AI_ASSIST_SYSTEM_PROMPT) < 500
        assert "JSON" in AI_ASSIST_SYSTEM_PROMPT

    def test_planning_prompt_is_minimal(self):
        """Test planning prompt is concise."""
        # Should be under 1000 chars (longer than others but still minimal)
        assert len(PLANNING_SYSTEM_PROMPT) < 1000
        assert "SheetSmith" in PLANNING_SYSTEM_PROMPT
        assert "formulas" in PLANNING_SYSTEM_PROMPT

    def test_all_prompts_different(self):
        """Test all prompts are distinct."""
        assert PARSER_SYSTEM_PROMPT != AI_ASSIST_SYSTEM_PROMPT
        assert PARSER_SYSTEM_PROMPT != PLANNING_SYSTEM_PROMPT
        assert AI_ASSIST_SYSTEM_PROMPT != PLANNING_SYSTEM_PROMPT
