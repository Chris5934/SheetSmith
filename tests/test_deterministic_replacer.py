"""Tests for deterministic formula replacement engine."""

import pytest
from unittest.mock import Mock

from sheetsmith.engine.replace import (
    DeterministicReplacer,
    ReplacementPlan,
)
from sheetsmith.sheets.models import FormulaMatch


@pytest.fixture
def mock_sheets_client():
    """Create a mocked Google Sheets client."""
    client = Mock()
    return client


@pytest.fixture
def replacer(mock_sheets_client):
    """Create a DeterministicReplacer instance with mocked client."""
    return DeterministicReplacer(mock_sheets_client)


class TestDeterministicReplacer:
    """Tests for the DeterministicReplacer class."""

    def test_simple_replacement(self, replacer, mock_sheets_client):
        """Test a simple exact string replacement."""
        # Mock search results
        mock_sheets_client.search_formulas.return_value = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell="A1",
                row=1,
                col=0,
                formula="=VLOOKUP(A2, B:C, 2, FALSE)",
                matched_text="VLOOKUP",
            ),
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell="A2",
                row=2,
                col=0,
                formula="=VLOOKUP(A3, D:E, 2, FALSE)",
                matched_text="VLOOKUP",
            ),
        ]

        # Mock batch update
        mock_result = Mock(success=True, updated_cells=2, errors=[])
        mock_sheets_client.batch_update.return_value = mock_result

        # Create plan
        plan = ReplacementPlan(
            action="replace",
            search_pattern="VLOOKUP",
            replace_with="XLOOKUP",
            case_sensitive=False,
            is_regex=False,
            dry_run=False,
        )

        # Execute
        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Replace VLOOKUP with XLOOKUP",
        )

        # Verify
        assert result.success is True
        assert result.matches_found == 2
        assert result.cells_updated == 2
        assert "Sheet1" in result.affected_sheets
        assert result.error is None

        # Verify the batch_update was called with correct formulas
        batch_call = mock_sheets_client.batch_update.call_args[0][0]
        assert len(batch_call.updates) == 2
        assert batch_call.updates[0].new_formula == "=XLOOKUP(A2, B:C, 2, FALSE)"
        assert batch_call.updates[1].new_formula == "=XLOOKUP(A3, D:E, 2, FALSE)"

    def test_case_insensitive_replacement(self, replacer, mock_sheets_client):
        """Test case-insensitive replacement."""
        # Mock search results with mixed case
        mock_sheets_client.search_formulas.return_value = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell="A1",
                row=1,
                col=0,
                formula="=vlookup(A2, B:C, 2, FALSE)",
                matched_text="vlookup",
            ),
        ]

        # Mock batch update
        mock_result = Mock(success=True, updated_cells=1, errors=[])
        mock_sheets_client.batch_update.return_value = mock_result

        # Create plan
        plan = ReplacementPlan(
            action="replace",
            search_pattern="VLOOKUP",
            replace_with="XLOOKUP",
            case_sensitive=False,
            is_regex=False,
            dry_run=False,
        )

        # Execute
        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Replace VLOOKUP with XLOOKUP (case-insensitive)",
        )

        # Verify replacement happened despite case difference
        assert result.success is True
        assert result.cells_updated == 1

    def test_regex_replacement(self, replacer, mock_sheets_client):
        """Test regex-based replacement."""
        # Mock search results
        mock_sheets_client.search_formulas.return_value = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell="A1",
                row=1,
                col=0,
                formula="=SUM(A1:A10) * 28.6%",
                matched_text="28.6%",
            ),
        ]

        # Mock batch update
        mock_result = Mock(success=True, updated_cells=1, errors=[])
        mock_sheets_client.batch_update.return_value = mock_result

        # Create plan with regex
        plan = ReplacementPlan(
            action="replace",
            search_pattern=r"28\.6%",
            replace_with="30.0%",
            case_sensitive=False,
            is_regex=True,
            dry_run=False,
        )

        # Execute
        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Update percentage from 28.6% to 30.0%",
        )

        # Verify
        assert result.success is True
        assert result.cells_updated == 1

        # Verify the formula was updated correctly
        batch_call = mock_sheets_client.batch_update.call_args[0][0]
        assert batch_call.updates[0].new_formula == "=SUM(A1:A10) * 30.0%"

    def test_dry_run_mode(self, replacer, mock_sheets_client):
        """Test dry run mode (preview without applying)."""
        # Mock search results
        mock_sheets_client.search_formulas.return_value = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell="A1",
                row=1,
                col=0,
                formula="=VLOOKUP(A2, B:C, 2, FALSE)",
                matched_text="VLOOKUP",
            ),
        ]

        # Create plan with dry_run=True
        plan = ReplacementPlan(
            action="replace",
            search_pattern="VLOOKUP",
            replace_with="XLOOKUP",
            case_sensitive=False,
            is_regex=False,
            dry_run=True,
        )

        # Execute
        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Preview VLOOKUP replacement",
        )

        # Verify preview is generated but no update was made
        assert result.success is True
        assert result.matches_found == 1
        assert result.cells_updated == 0  # No actual update in dry_run
        assert result.preview is not None
        assert "Sheet1!A1" in result.preview
        assert "XLOOKUP" in result.preview

        # Verify batch_update was NOT called
        mock_sheets_client.batch_update.assert_not_called()

    def test_target_specific_sheets(self, replacer, mock_sheets_client):
        """Test targeting specific sheets for replacement."""
        # Mock search results
        mock_sheets_client.search_formulas.return_value = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell="A1",
                row=1,
                col=0,
                formula="=VLOOKUP(A2, B:C, 2, FALSE)",
                matched_text="VLOOKUP",
            ),
        ]

        # Mock batch update
        mock_result = Mock(success=True, updated_cells=1, errors=[])
        mock_sheets_client.batch_update.return_value = mock_result

        # Create plan targeting specific sheet
        plan = ReplacementPlan(
            action="replace",
            search_pattern="VLOOKUP",
            replace_with="XLOOKUP",
            target_sheets=["Sheet1"],
            case_sensitive=False,
            is_regex=False,
            dry_run=False,
        )

        # Execute
        _ = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Replace VLOOKUP in Sheet1 only",
        )

        # Verify search was called with correct sheet filter
        mock_sheets_client.search_formulas.assert_called_once()
        call_args = mock_sheets_client.search_formulas.call_args
        assert call_args[1]["sheet_names"] == ["Sheet1"]

    def test_no_matches_found(self, replacer, mock_sheets_client):
        """Test behavior when no matches are found."""
        # Mock empty search results
        mock_sheets_client.search_formulas.return_value = []

        # Create plan
        plan = ReplacementPlan(
            action="replace",
            search_pattern="NONEXISTENT",
            replace_with="SOMETHING",
            case_sensitive=False,
            is_regex=False,
            dry_run=False,
        )

        # Execute
        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Replace something that doesn't exist",
        )

        # Verify graceful handling
        assert result.success is True
        assert result.matches_found == 0
        assert result.cells_updated == 0
        assert len(result.affected_sheets) == 0

        # Verify batch_update was NOT called
        mock_sheets_client.batch_update.assert_not_called()


class TestCanHandleDeterministically:
    """Tests for determining if a request can be handled deterministically."""

    def test_simple_replace_request(self):
        """Test detection of simple replace requests."""
        assert DeterministicReplacer.can_handle_deterministically("Replace VLOOKUP with XLOOKUP")
        assert DeterministicReplacer.can_handle_deterministically("Change 28.6% to 30.0%")
        assert DeterministicReplacer.can_handle_deterministically(
            "Update Corruption to Enhanced Corruption"
        )

    def test_complex_request_needs_llm(self):
        """Test detection of complex requests that need LLM."""
        assert not DeterministicReplacer.can_handle_deterministically(
            "Refactor the formula to use INDIRECT instead"
        )
        assert not DeterministicReplacer.can_handle_deterministically(
            "Fix the logic in the damage calculation"
        )
        assert not DeterministicReplacer.can_handle_deterministically(
            "Optimize the performance of this formula"
        )

    def test_ambiguous_requests(self):
        """Test detection of ambiguous requests."""
        # These could be deterministic but lack clear "X to Y" pattern
        assert not DeterministicReplacer.can_handle_deterministically("Update the damage formula")
        assert not DeterministicReplacer.can_handle_deterministically("Change the calculations")


class TestParseSimpleReplacement:
    """Tests for parsing simple replacement requests."""

    def test_parse_replace_with_pattern(self):
        """Test parsing 'replace X with Y' pattern."""
        plan = DeterministicReplacer.parse_simple_replacement("Replace VLOOKUP with XLOOKUP")
        assert plan is not None
        assert plan.search_pattern == "VLOOKUP"
        assert plan.replace_with == "XLOOKUP"
        assert plan.target_sheets is None

    def test_parse_change_to_pattern(self):
        """Test parsing 'change X to Y' pattern."""
        plan = DeterministicReplacer.parse_simple_replacement("Change 28.6% to 30.0%")
        assert plan is not None
        assert plan.search_pattern == "28.6%"
        assert plan.replace_with == "30.0%"

    def test_parse_update_to_pattern(self):
        """Test parsing 'update X to Y' pattern."""
        plan = DeterministicReplacer.parse_simple_replacement(
            "Update Corruption to Enhanced Corruption"
        )
        assert plan is not None
        assert plan.search_pattern == "Corruption"
        assert plan.replace_with == "Enhanced Corruption"

    def test_parse_with_target_sheet(self):
        """Test parsing requests with target sheet specification."""
        plan = DeterministicReplacer.parse_simple_replacement(
            "Replace VLOOKUP with XLOOKUP in Sheet1"
        )
        assert plan is not None
        assert plan.search_pattern == "VLOOKUP"
        assert plan.replace_with == "XLOOKUP"
        assert plan.target_sheets == ["Sheet1"]

    def test_parse_with_multiple_sheets(self):
        """Test parsing requests with multiple target sheets."""
        plan = DeterministicReplacer.parse_simple_replacement(
            "Replace VLOOKUP with XLOOKUP in Sheet1 and Sheet2"
        )
        assert plan is not None
        assert plan.search_pattern == "VLOOKUP"
        assert plan.replace_with == "XLOOKUP"
        # Should extract both sheet names
        assert "Sheet1" in plan.target_sheets
        assert "Sheet2" in plan.target_sheets

    def test_parse_with_quotes(self):
        """Test parsing requests with quoted strings."""
        plan = DeterministicReplacer.parse_simple_replacement(
            'Replace "Corruption" with "Enhanced Corruption"'
        )
        assert plan is not None
        assert plan.search_pattern == "Corruption"
        assert plan.replace_with == "Enhanced Corruption"

    def test_unparseable_request(self):
        """Test handling of unparseable requests."""
        plan = DeterministicReplacer.parse_simple_replacement("Do something complicated")
        assert plan is None

        plan = DeterministicReplacer.parse_simple_replacement("Fix the formulas")
        assert plan is None
