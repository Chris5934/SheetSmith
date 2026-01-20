"""Tests for the agent prompts."""

from sheetsmith.agent.prompts import SYSTEM_PROMPT, TASK_PROMPTS


class TestSystemPrompt:
    """Test the system prompt structure and content."""

    def test_prompt_contains_tool_selection_section(self):
        """Test that the prompt contains the critical tool selection section."""
        assert "CRITICAL: TOOL SELECTION" in SYSTEM_PROMPT
        assert "TOOL SELECTION DECISION TREE" in SYSTEM_PROMPT

    def test_prompt_contains_cost_warning(self):
        """Test that the prompt contains cost efficiency warnings."""
        assert "COST WARNING" in SYSTEM_PROMPT
        assert "wastes user money" in SYSTEM_PROMPT

    def test_prompt_contains_mass_replace_examples(self):
        """Test that the prompt contains concrete examples for mass_replace."""
        # Check for the SEED sheet reference example from the problem statement
        assert "SEED" in SYSTEM_PROMPT
        assert "Base" in SYSTEM_PROMPT

        # Check for other key examples
        assert "VLOOKUP" in SYSTEM_PROMPT
        assert "XLOOKUP" in SYSTEM_PROMPT
        assert "28.6%" in SYSTEM_PROMPT
        assert "30.0%" in SYSTEM_PROMPT

    def test_prompt_has_decision_rule(self):
        """Test that the prompt has a clear decision rule."""
        assert "DECISION RULE" in SYSTEM_PROMPT
        assert "replace string A with string B" in SYSTEM_PROMPT

    def test_prompt_prioritizes_mass_replace(self):
        """Test that mass_replace is mentioned early and emphasized."""
        # The tool selection section should appear before the general workflow
        tool_selection_pos = SYSTEM_PROMPT.find("TOOL SELECTION DECISION TREE")
        workflow_pos = SYSTEM_PROMPT.find("When a user asks to update a formula pattern")

        assert tool_selection_pos > 0, "Tool selection section not found"
        assert workflow_pos > 0, "Workflow section not found"
        assert tool_selection_pos < workflow_pos, "Tool selection should come before workflow"

    def test_prompt_contains_concrete_user_examples(self):
        """Test that the prompt contains concrete user request examples."""
        # Examples from the problem statement
        assert "Fix formulas that reference SEED sheet" in SYSTEM_PROMPT
        assert "Replace SEED! with Base!" in SYSTEM_PROMPT
        assert "Update all VLOOKUP to XLOOKUP" in SYSTEM_PROMPT
        assert "Change 28.6% to 30.0%" in SYSTEM_PROMPT

    def test_prompt_shows_when_not_to_use_mass_replace(self):
        """Test that the prompt also shows negative examples."""
        assert "Update the damage formula to include" in SYSTEM_PROMPT
        assert "manual processing" in SYSTEM_PROMPT

    def test_prompt_includes_workflow_steps(self):
        """Test that the prompt includes the formula.mass_replace workflow."""
        assert "dry_run=true" in SYSTEM_PROMPT
        assert "dry_run=false" in SYSTEM_PROMPT
        assert "preview" in SYSTEM_PROMPT

    def test_prompt_emphasizes_cost_efficiency(self):
        """Test that cost efficiency is emphasized throughout."""
        # Should mention 99% cost reduction
        assert "99%" in SYSTEM_PROMPT
        # Should mention it in key principles
        assert "Cost efficiency" in SYSTEM_PROMPT or "cost efficiency" in SYSTEM_PROMPT

    def test_prompt_mentions_formula_mass_replace_tool(self):
        """Test that the prompt explicitly mentions the tool name."""
        assert "formula.mass_replace" in SYSTEM_PROMPT


class TestTaskPrompts:
    """Test the task-specific prompts."""

    def test_update_value_prompt_prioritizes_mass_replace(self):
        """Test that update_value task prompt mentions mass_replace first."""
        update_value_prompt = TASK_PROMPTS["update_value"]

        # Should mention determining if it's a simple replacement
        assert "simple replacement" in update_value_prompt
        assert "formula.mass_replace" in update_value_prompt

    def test_update_value_prompt_has_two_paths(self):
        """Test that update_value has both simple and complex paths."""
        update_value_prompt = TASK_PROMPTS["update_value"]

        # Should have path for simple replacements
        assert "For simple replacements" in update_value_prompt
        # Should have path for complex replacements
        assert "For complex replacements" in update_value_prompt

    def test_all_task_prompts_exist(self):
        """Test that all expected task prompts are defined."""
        assert "update_value" in TASK_PROMPTS
        assert "audit_formulas" in TASK_PROMPTS
        assert "replace_logic" in TASK_PROMPTS

    def test_task_prompts_are_strings(self):
        """Test that all task prompts are strings."""
        for prompt_name, prompt_content in TASK_PROMPTS.items():
            assert isinstance(prompt_content, str), f"{prompt_name} should be a string"
            assert len(prompt_content) > 0, f"{prompt_name} should not be empty"


class TestPromptStructure:
    """Test the overall structure and formatting of prompts."""

    def test_system_prompt_is_multiline_string(self):
        """Test that SYSTEM_PROMPT is a properly formatted string."""
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100
        assert "\n" in SYSTEM_PROMPT

    def test_prompt_has_clear_sections(self):
        """Test that the prompt is organized into clear sections."""
        # Should have visual separators for key sections
        assert "═══" in SYSTEM_PROMPT  # Section separators

        # Should have emoji or other visual markers for emphasis
        assert "🚨" in SYSTEM_PROMPT or "⚠️" in SYSTEM_PROMPT or "✅" in SYSTEM_PROMPT

    def test_prompt_has_examples_formatted_clearly(self):
        """Test that examples are clearly formatted."""
        # Should use clear formatting like arrows or indicators
        assert "→" in SYSTEM_PROMPT or "->" in SYSTEM_PROMPT
        assert "✅" in SYSTEM_PROMPT or "❌" in SYSTEM_PROMPT

    def test_prompt_balances_length_and_completeness(self):
        """Test that the prompt is comprehensive but not excessively long."""
        # Should be substantial (at least 2000 chars to cover all details)
        assert len(SYSTEM_PROMPT) > 2000
        # But not so long as to be unwieldy (less than 8000 chars)
        assert len(SYSTEM_PROMPT) < 8000
