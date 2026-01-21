"""Tests for safety features including models, checker, and integration."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from sheetsmith.ops.safety_models import (
    PreviewDiff,
    ScopeSummary,
    SafetyCheck,
    MappingAuditEntry,
    AuditReport,
)
from sheetsmith.ops.safety_checker import SafetyChecker
from sheetsmith.ops.models import Operation, OperationType, SearchCriteria
from sheetsmith.config import settings


class TestSafetyModels:
    """Tests for safety model classes."""

    def test_preview_diff_creation(self):
        """Test creating a PreviewDiff model."""
        diff = PreviewDiff(
            cell_address="A1",
            sheet_name="Sheet1",
            header_name="Name",
            row_label="Row1",
            before_value="Old",
            after_value="New",
            before_formula=None,
            after_formula=None,
            change_type="value",
        )

        assert diff.cell_address == "A1"
        assert diff.sheet_name == "Sheet1"
        assert diff.header_name == "Name"
        assert diff.change_type == "value"

    def test_scope_summary_creation(self):
        """Test creating a ScopeSummary model."""
        scope = ScopeSummary(
            total_cells=100,
            total_sheets=2,
            sheet_names=["Sheet1", "Sheet2"],
            headers_affected=["Name", "Amount"],
            row_range_by_sheet={"Sheet1": (1, 50), "Sheet2": (1, 50)},
            formula_patterns_matched=["SUM"],
            estimated_duration_seconds=1.0,
        )

        assert scope.total_cells == 100
        assert scope.total_sheets == 2
        assert len(scope.sheet_names) == 2
        assert scope.estimated_duration_seconds == 1.0

    def test_safety_check_passed(self):
        """Test safety check that passes."""
        check = SafetyCheck(
            passed=True,
            warnings=["Minor warning"],
            errors=[],
            limit_breaches=[],
            ambiguities=[],
        )

        assert check.passed is True
        assert len(check.warnings) == 1
        assert len(check.errors) == 0

    def test_safety_check_failed(self):
        """Test safety check that fails."""
        check = SafetyCheck(
            passed=False,
            warnings=[],
            errors=["Hard limit breached"],
            limit_breaches=["max_cells_per_operation"],
            ambiguities=[],
        )

        assert check.passed is False
        assert len(check.errors) == 1
        assert len(check.limit_breaches) == 1

    def test_audit_report_creation(self):
        """Test creating an AuditReport."""
        report = AuditReport(
            timestamp=datetime.utcnow().isoformat(),
            spreadsheet_id="test-123",
            mappings_checked=10,
            valid_mappings=8,
            invalid_mappings=[
                MappingAuditEntry(
                    mapping_type="column",
                    sheet_name="Sheet1",
                    header_text="Name",
                    status="missing",
                )
            ],
            warnings=["2 mappings invalid"],
            recommendations=["Clear invalid mappings"],
        )

        assert report.spreadsheet_id == "test-123"
        assert report.mappings_checked == 10
        assert report.valid_mappings == 8
        assert len(report.invalid_mappings) == 1


class TestSafetyChecker:
    """Tests for SafetyChecker class."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked Google Sheets client."""
        return Mock()

    @pytest.fixture
    def safety_checker(self, mock_sheets_client):
        """Create a SafetyChecker instance."""
        return SafetyChecker(mock_sheets_client)

    def test_enforce_hard_limits_within_limits(self, safety_checker):
        """Test that enforcement passes when within limits."""
        scope = ScopeSummary(
            total_cells=10,  # Well under limit
            total_sheets=2,
            sheet_names=["Sheet1", "Sheet2"],
            headers_affected=["Name"],
            formula_patterns_matched=[],
        )

        # Should not raise exception
        safety_checker.enforce_hard_limits(scope)

    def test_enforce_hard_limits_exceeds_cells(self, safety_checker):
        """Test that enforcement fails when cells limit exceeded."""
        scope = ScopeSummary(
            total_cells=settings.max_cells_per_operation + 1,
            total_sheets=2,
            sheet_names=["Sheet1", "Sheet2"],
            headers_affected=["Name"],
            formula_patterns_matched=[],
        )

        with pytest.raises(ValueError) as exc_info:
            safety_checker.enforce_hard_limits(scope)

        # Check that the error message mentions cells and the limit
        assert "cells" in str(exc_info.value).lower()
        assert str(settings.max_cells_per_operation) in str(exc_info.value)

    def test_enforce_hard_limits_exceeds_sheets(self, safety_checker):
        """Test that enforcement fails when sheets limit exceeded."""
        scope = ScopeSummary(
            total_cells=10,
            total_sheets=settings.max_sheets_per_operation + 1,
            sheet_names=[f"Sheet{i}" for i in range(settings.max_sheets_per_operation + 1)],
            headers_affected=["Name"],
            formula_patterns_matched=[],
        )

        with pytest.raises(ValueError) as exc_info:
            safety_checker.enforce_hard_limits(scope)

        # Check that the error message mentions sheets and the limit
        assert "sheets" in str(exc_info.value).lower()
        assert str(settings.max_sheets_per_operation) in str(exc_info.value)

    def test_enforce_hard_limits_formula_too_long(self, safety_checker):
        """Test that enforcement fails when formula pattern too long."""
        long_pattern = "A" * (settings.max_formula_length + 1)
        scope = ScopeSummary(
            total_cells=10,
            total_sheets=1,
            sheet_names=["Sheet1"],
            headers_affected=["Name"],
            formula_patterns_matched=[long_pattern],
        )

        with pytest.raises(ValueError) as exc_info:
            safety_checker.enforce_hard_limits(scope)

        assert "formula pattern length" in str(exc_info.value).lower()

    def test_check_operation_safety_passes(self, safety_checker):
        """Test safety check passes for valid operation."""
        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Test operation",
            find_pattern="SUM",
            replace_with="SUMIF",
        )

        scope = ScopeSummary(
            total_cells=5,
            total_sheets=1,
            sheet_names=["Sheet1"],
            headers_affected=["Amount"],
            formula_patterns_matched=["SUM"],
        )

        check = safety_checker.check_operation_safety(operation, scope)

        assert check.passed is True
        assert len(check.errors) == 0

    def test_check_operation_safety_fails_on_limit(self, safety_checker):
        """Test safety check fails when limit breached."""
        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Test operation",
            find_pattern="SUM",
            replace_with="SUMIF",
        )

        scope = ScopeSummary(
            total_cells=settings.max_cells_per_operation + 1,
            total_sheets=1,
            sheet_names=["Sheet1"],
            headers_affected=["Amount"],
            formula_patterns_matched=["SUM"],
        )

        check = safety_checker.check_operation_safety(operation, scope)

        assert check.passed is False
        assert len(check.errors) > 0
        assert len(check.limit_breaches) > 0

    def test_check_operation_safety_warning_large_op(self, safety_checker):
        """Test safety check adds warning for large operations."""
        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Test operation",
            find_pattern="SUM",
            replace_with="SUMIF",
        )

        scope = ScopeSummary(
            total_cells=settings.require_preview_above_cells + 5,
            total_sheets=1,
            sheet_names=["Sheet1"],
            headers_affected=["Amount"],
            formula_patterns_matched=["SUM"],
        )

        check = safety_checker.check_operation_safety(operation, scope)

        # Should pass but have warnings
        assert check.passed is True
        assert len(check.warnings) > 0
        assert any("exceeds the recommended threshold" in w for w in check.warnings)

    def test_validate_mappings_returns_report(self, safety_checker):
        """Test that validate_mappings returns a report."""
        report = safety_checker.validate_mappings("test-spreadsheet-123")

        assert isinstance(report, AuditReport)
        assert report.spreadsheet_id == "test-spreadsheet-123"
        assert report.timestamp is not None
        assert report.mappings_checked >= 0

    def test_detect_header_ambiguities_empty(self, safety_checker):
        """Test ambiguity detection with no sheets."""
        ambiguities = safety_checker.detect_header_ambiguities([], ["Name"])

        assert isinstance(ambiguities, list)
        assert len(ambiguities) == 0


class TestSafetyIntegration:
    """Integration tests for safety features with operations."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked Google Sheets client."""
        from sheetsmith.sheets.models import CellData, SheetRange

        client = Mock()
        client.get_spreadsheet_info = Mock(
            return_value={
                "id": "test-sheet-123",
                "title": "Test Sheet",
                "sheets": [
                    {
                        "title": "Sheet1",
                        "id": 0,
                        "row_count": 100,
                        "col_count": 26,
                    }
                ],
            }
        )

        client.read_range = Mock(
            return_value=SheetRange(
                spreadsheet_id="test-sheet-123",
                sheet_name="Sheet1",
                range_notation="Sheet1!A1:Z100",
                cells=[
                    CellData(
                        sheet_name="Sheet1",
                        cell="B2",
                        row=2,
                        col=1,
                        value=100,
                        formula="=SUM(C2:D2)",
                    ),
                ],
            )
        )

        return client

    def test_preview_with_safety_checks(self, mock_sheets_client):
        """Test that preview generation includes safety checks."""
        from sheetsmith.ops.preview import PreviewGenerator
        from sheetsmith.ops.search import CellSearchEngine

        search_engine = CellSearchEngine(mock_sheets_client)
        generator = PreviewGenerator(mock_sheets_client, search_engine)

        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Test operation",
            find_pattern="SUM",
            replace_with="SUMIF",
        )

        preview = generator.generate_preview("test-sheet-123", operation)

        # Preview should be generated
        assert preview is not None
        assert preview.preview_id is not None
        assert preview.operation_type == OperationType.REPLACE_IN_FORMULAS

    def test_dry_run_preview(self, mock_sheets_client):
        """Test dry-run mode in preview generation."""
        from sheetsmith.ops.preview import PreviewGenerator
        from sheetsmith.ops.search import CellSearchEngine

        search_engine = CellSearchEngine(mock_sheets_client)
        generator = PreviewGenerator(mock_sheets_client, search_engine)

        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Test dry-run operation",
            find_pattern="SUM",
            replace_with="SUMIF",
        )

        preview = generator.generate_preview(
            "test-sheet-123", operation, dry_run=True
        )

        # Preview should be generated even in dry-run
        assert preview is not None
        assert preview.preview_id is not None
