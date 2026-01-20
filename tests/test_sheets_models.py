"""Tests for sheets models."""

import pytest

from sheetsmith.sheets.models import BatchUpdate, CellUpdate


class TestBatchUpdate:
    """Test the BatchUpdate model."""

    def test_batch_update_creation(self):
        """Test creating a BatchUpdate."""
        batch = BatchUpdate(
            spreadsheet_id="test-123",
            description="Test batch",
        )

        assert batch.spreadsheet_id == "test-123"
        assert batch.description == "Test batch"
        assert batch.updates == []

    def test_add_update(self):
        """Test adding updates to a batch."""
        batch = BatchUpdate(spreadsheet_id="test-123")

        batch.add_update(
            sheet_name="Sheet1",
            cell="A1",
            new_value="Test",
        )
        batch.add_update(
            sheet_name="Sheet1",
            cell="B1",
            new_formula="=SUM(A1:A10)",
        )

        assert len(batch.updates) == 2
        assert batch.updates[0].sheet_name == "Sheet1"
        assert batch.updates[0].cell == "A1"
        assert batch.updates[0].new_value == "Test"
        assert batch.updates[1].new_formula == "=SUM(A1:A10)"

    def test_get_statistics_empty_batch(self):
        """Test get_statistics with empty batch."""
        batch = BatchUpdate(spreadsheet_id="test-123")

        stats = batch.get_statistics()

        assert stats["total_cells"] == 0
        assert stats["affected_sheets"] == []
        assert stats["affected_columns"] == []
        assert stats["sheet_count"] == 0
        assert stats["column_count"] == 0

    def test_get_statistics_single_sheet_single_column(self):
        """Test get_statistics with updates in one sheet and one column."""
        batch = BatchUpdate(spreadsheet_id="test-123")

        batch.add_update(sheet_name="Sheet1", cell="A1", new_value="Test1")
        batch.add_update(sheet_name="Sheet1", cell="A2", new_value="Test2")
        batch.add_update(sheet_name="Sheet1", cell="A3", new_value="Test3")

        stats = batch.get_statistics()

        assert stats["total_cells"] == 3
        assert stats["affected_sheets"] == ["Sheet1"]
        assert stats["affected_columns"] == ["A"]
        assert stats["sheet_count"] == 1
        assert stats["column_count"] == 1

    def test_get_statistics_single_sheet_multiple_columns(self):
        """Test get_statistics with updates in one sheet but multiple columns."""
        batch = BatchUpdate(spreadsheet_id="test-123")

        batch.add_update(sheet_name="Sheet1", cell="A1", new_value="Test1")
        batch.add_update(sheet_name="Sheet1", cell="B1", new_value="Test2")
        batch.add_update(sheet_name="Sheet1", cell="C1", new_value="Test3")
        batch.add_update(sheet_name="Sheet1", cell="D1", new_value="Test4")

        stats = batch.get_statistics()

        assert stats["total_cells"] == 4
        assert stats["affected_sheets"] == ["Sheet1"]
        assert stats["affected_columns"] == ["A", "B", "C", "D"]
        assert stats["sheet_count"] == 1
        assert stats["column_count"] == 4

    def test_get_statistics_multiple_sheets(self):
        """Test get_statistics with updates across multiple sheets."""
        batch = BatchUpdate(spreadsheet_id="test-123")

        batch.add_update(sheet_name="Summary", cell="A1", new_value="Test1")
        batch.add_update(sheet_name="Summary", cell="B1", new_value="Test2")
        batch.add_update(sheet_name="Data", cell="A1", new_value="Test3")
        batch.add_update(sheet_name="Data", cell="C1", new_value="Test4")
        batch.add_update(sheet_name="Reports", cell="A1", new_value="Test5")

        stats = batch.get_statistics()

        assert stats["total_cells"] == 5
        assert stats["affected_sheets"] == ["Data", "Reports", "Summary"]
        assert stats["affected_columns"] == ["A", "B", "C"]
        assert stats["sheet_count"] == 3
        assert stats["column_count"] == 3

    def test_get_statistics_with_multi_letter_columns(self):
        """Test get_statistics with multi-letter column references like AA, AB."""
        batch = BatchUpdate(spreadsheet_id="test-123")

        batch.add_update(sheet_name="Sheet1", cell="A1", new_value="Test1")
        batch.add_update(sheet_name="Sheet1", cell="Z1", new_value="Test2")
        batch.add_update(sheet_name="Sheet1", cell="AA1", new_value="Test3")
        batch.add_update(sheet_name="Sheet1", cell="AB1", new_value="Test4")

        stats = batch.get_statistics()

        assert stats["total_cells"] == 4
        assert stats["affected_columns"] == ["A", "AA", "AB", "Z"]
        assert stats["column_count"] == 4

    def test_get_statistics_complex_scenario(self):
        """Test get_statistics with a complex real-world scenario."""
        batch = BatchUpdate(
            spreadsheet_id="test-123",
            description="Update damage formulas",
        )

        # Add multiple updates simulating a formula update across sheets
        for i in range(1, 11):
            batch.add_update(
                sheet_name="Summary",
                cell=f"D{i}",
                new_formula=f"=VLOOKUP(A{i}, Data!A:B, 2, FALSE)",
            )
            batch.add_update(
                sheet_name="Summary",
                cell=f"E{i}",
                new_formula=f"=VLOOKUP(A{i}, Data!A:C, 3, FALSE)",
            )

        for i in range(1, 6):
            batch.add_update(
                sheet_name="Data",
                cell=f"F{i}",
                new_value=f"Updated value {i}",
            )

        stats = batch.get_statistics()

        assert stats["total_cells"] == 25
        assert stats["affected_sheets"] == ["Data", "Summary"]
        assert stats["affected_columns"] == ["D", "E", "F"]
        assert stats["sheet_count"] == 2
        assert stats["column_count"] == 3

    def test_get_statistics_duplicate_cells_counted_separately(self):
        """Test that duplicate cell references are counted separately."""
        batch = BatchUpdate(spreadsheet_id="test-123")

        # Add the same cell twice (which shouldn't happen in practice but tests the counting)
        batch.add_update(sheet_name="Sheet1", cell="A1", new_value="First")
        batch.add_update(sheet_name="Sheet1", cell="A1", new_value="Second")

        stats = batch.get_statistics()

        # Both updates should be counted
        assert stats["total_cells"] == 2
        assert stats["affected_sheets"] == ["Sheet1"]
        assert stats["affected_columns"] == ["A"]
        assert stats["sheet_count"] == 1
        assert stats["column_count"] == 1


class TestCellUpdate:
    """Test the CellUpdate model."""

    def test_cell_update_range_notation(self):
        """Test that range_notation property works correctly."""
        update = CellUpdate(
            sheet_name="Sheet1",
            cell="A1",
            new_value="Test",
        )

        assert update.range_notation == "Sheet1!A1"

    def test_cell_update_range_notation_with_formula(self):
        """Test range_notation with formula."""
        update = CellUpdate(
            sheet_name="Data",
            cell="B5",
            new_formula="=SUM(A1:A10)",
        )

        assert update.range_notation == "Data!B5"
