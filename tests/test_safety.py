"""Tests for safety validator."""

import pytest
from unittest.mock import Mock, patch

from sheetsmith.engine.safety import SafetyValidator, SafetyViolation
from sheetsmith.engine.replace import DeterministicReplacer, ReplacementPlan
from sheetsmith.sheets.models import FormulaMatch


class TestSafetyValidator:
    """Tests for the SafetyValidator class."""

    def test_validate_operation_within_limits(self):
        """Test operation within all safety limits."""
        validator = SafetyValidator()

        is_safe, violations = validator.validate_operation(
            cells_affected=10,
            sheets_affected=5,
        )

        assert is_safe is True
        assert len(violations) == 0

    def test_validate_operation_exceeds_cells_limit(self):
        """Test operation exceeding max cells limit."""
        validator = SafetyValidator()

        is_safe, violations = validator.validate_operation(
            cells_affected=1000,
            sheets_affected=5,
        )

        assert is_safe is False
        assert len(violations) == 1
        assert violations[0].constraint == "max_cells_per_operation"
        assert violations[0].current_value == 1000
        assert "exceeding limit" in violations[0].message

    def test_validate_operation_exceeds_sheets_limit(self):
        """Test operation exceeding max sheets limit."""
        validator = SafetyValidator()

        is_safe, violations = validator.validate_operation(
            cells_affected=10,
            sheets_affected=50,
        )

        assert is_safe is False
        assert len(violations) == 1
        assert violations[0].constraint == "max_sheets_per_operation"
        assert violations[0].current_value == 50
        assert "exceeding limit" in violations[0].message

    def test_validate_operation_exceeds_formula_length(self):
        """Test operation with formula exceeding max length."""
        validator = SafetyValidator()

        is_safe, violations = validator.validate_operation(
            cells_affected=10,
            sheets_affected=5,
            max_formula_length=60000,
        )

        assert is_safe is False
        assert len(violations) == 1
        assert violations[0].constraint == "max_formula_length"
        assert violations[0].current_value == 60000
        assert "exceeds limit" in violations[0].message

    def test_validate_operation_multiple_violations(self):
        """Test operation with multiple constraint violations."""
        validator = SafetyValidator()

        is_safe, violations = validator.validate_operation(
            cells_affected=1000,
            sheets_affected=50,
            max_formula_length=60000,
        )

        assert is_safe is False
        assert len(violations) == 3
        constraints = [v.constraint for v in violations]
        assert "max_cells_per_operation" in constraints
        assert "max_sheets_per_operation" in constraints
        assert "max_formula_length" in constraints

    def test_requires_preview_below_threshold(self):
        """Test preview not required below threshold."""
        validator = SafetyValidator()

        assert validator.requires_preview(5) is False
        assert validator.requires_preview(10) is False

    def test_requires_preview_above_threshold(self):
        """Test preview required above threshold."""
        validator = SafetyValidator()

        assert validator.requires_preview(11) is True
        assert validator.requires_preview(100) is True


class TestDeterministicReplacerSafety:
    """Tests for safety integration with DeterministicReplacer."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked Google Sheets client."""
        client = Mock()
        return client

    @pytest.fixture
    def replacer(self, mock_sheets_client):
        """Create a DeterministicReplacer instance with mocked client."""
        return DeterministicReplacer(mock_sheets_client)

    def test_replacement_blocked_by_cells_limit(self, replacer, mock_sheets_client):
        """Test that replacement is blocked when exceeding cells limit."""
        # Mock search results with too many matches
        matches = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell=f"A{i}",
                row=i,
                col=0,
                formula=f"=VLOOKUP(A{i+1}, B:C, 2, FALSE)",
                matched_text="VLOOKUP",
            )
            for i in range(1, 600)  # 599 matches, exceeds default limit of 500
        ]
        mock_sheets_client.search_formulas.return_value = matches

        plan = ReplacementPlan(
            action="replace",
            search_pattern="VLOOKUP",
            replace_with="XLOOKUP",
            case_sensitive=False,
            is_regex=False,
            dry_run=False,
        )

        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Replace VLOOKUP with XLOOKUP",
        )

        # Verify operation was blocked
        assert result.success is False
        assert result.matches_found == 599
        assert result.cells_updated == 0
        assert "Safety constraints violated" in result.error
        assert "exceeding limit" in result.error

    def test_replacement_blocked_by_sheets_limit(self, replacer, mock_sheets_client):
        """Test that replacement is blocked when exceeding sheets limit."""
        # Mock search results across too many sheets
        matches = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name=f"Sheet{i}",
                cell="A1",
                row=1,
                col=0,
                formula="=VLOOKUP(A2, B:C, 2, FALSE)",
                matched_text="VLOOKUP",
            )
            for i in range(1, 50)  # 49 sheets, exceeds default limit of 40
        ]
        mock_sheets_client.search_formulas.return_value = matches

        plan = ReplacementPlan(
            action="replace",
            search_pattern="VLOOKUP",
            replace_with="XLOOKUP",
            case_sensitive=False,
            is_regex=False,
            dry_run=False,
        )

        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Replace VLOOKUP with XLOOKUP",
        )

        # Verify operation was blocked
        assert result.success is False
        assert result.matches_found == 49
        assert result.cells_updated == 0
        assert "Safety constraints violated" in result.error

    def test_replacement_allowed_within_limits(self, replacer, mock_sheets_client):
        """Test that replacement is allowed when within safety limits."""
        # Mock search results within limits
        matches = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell=f"A{i}",
                row=i,
                col=0,
                formula=f"=VLOOKUP(A{i+1}, B:C, 2, FALSE)",
                matched_text="VLOOKUP",
            )
            for i in range(1, 11)  # 10 matches, well within limits
        ]
        mock_sheets_client.search_formulas.return_value = matches

        # Mock batch update
        mock_result = Mock(success=True, updated_cells=10, errors=[])
        mock_sheets_client.batch_update.return_value = mock_result

        plan = ReplacementPlan(
            action="replace",
            search_pattern="VLOOKUP",
            replace_with="XLOOKUP",
            case_sensitive=False,
            is_regex=False,
            dry_run=False,
        )

        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Replace VLOOKUP with XLOOKUP",
        )

        # Verify operation succeeded
        assert result.success is True
        assert result.matches_found == 10
        assert result.cells_updated == 10
        assert result.error is None

    def test_dry_run_not_blocked_by_limits(self, replacer, mock_sheets_client):
        """Test that dry_run preview is not blocked by safety limits."""
        # Mock search results exceeding limits
        matches = [
            FormulaMatch(
                spreadsheet_id="test-123",
                sheet_name="Sheet1",
                cell=f"A{i}",
                row=i,
                col=0,
                formula=f"=VLOOKUP(A{i+1}, B:C, 2, FALSE)",
                matched_text="VLOOKUP",
            )
            for i in range(1, 600)  # 599 matches
        ]
        mock_sheets_client.search_formulas.return_value = matches

        plan = ReplacementPlan(
            action="replace",
            search_pattern="VLOOKUP",
            replace_with="XLOOKUP",
            case_sensitive=False,
            is_regex=False,
            dry_run=True,  # Dry run should still be blocked
        )

        result = replacer.execute_replacement(
            spreadsheet_id="test-123",
            plan=plan,
            description="Replace VLOOKUP with XLOOKUP",
        )

        # Even dry runs should be blocked by safety constraints
        assert result.success is False
        assert "Safety constraints violated" in result.error
