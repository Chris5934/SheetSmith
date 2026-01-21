"""Tests for deterministic operations module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from sheetsmith.ops import (
    DeterministicOpsEngine,
    SearchRequest,
    SearchResult,
    PreviewRequest,
    ApplyRequest,
    OperationType,
)
from sheetsmith.ops.models import (
    SearchCriteria,
    CellMatch,
    Operation,
    ChangeSpec,
    ScopeInfo,
)
from sheetsmith.ops.cache import PreviewCache
from sheetsmith.sheets.models import CellData, SheetRange


@pytest.fixture
def mock_sheets_client():
    """Create a mocked Google Sheets client."""
    client = Mock()
    
    # Mock spreadsheet info
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
    
    # Mock read_range
    client.read_range = Mock(
        return_value=SheetRange(
            spreadsheet_id="test-sheet-123",
            sheet_name="Sheet1",
            range_notation="Sheet1!A1:Z100",
            cells=[
                CellData(
                    sheet_name="Sheet1",
                    cell="A1",
                    row=1,
                    col=0,
                    value="Name",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="B1",
                    row=1,
                    col=1,
                    value="Amount",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="A2",
                    row=2,
                    col=0,
                    value="Item1",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="B2",
                    row=2,
                    col=1,
                    value=100,
                    formula="=SUM(C2:D2)",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="A3",
                    row=3,
                    col=0,
                    value="Item2",
                ),
                CellData(
                    sheet_name="Sheet1",
                    cell="B3",
                    row=3,
                    col=1,
                    value=200,
                    formula="=SUM(C3:D3)",
                ),
            ],
        )
    )
    
    # Mock batch_update
    from sheetsmith.sheets.models import UpdateResult
    client.batch_update = Mock(
        return_value=UpdateResult(
            success=True,
            spreadsheet_id="test-sheet-123",
            updated_cells=2,
        )
    )
    
    return client


@pytest.fixture
async def mock_memory_store(tmp_path):
    """Create a mocked memory store."""
    from typing import AsyncGenerator
    from sheetsmith.memory import MemoryStore
    
    db_path = tmp_path / "test_ops.db"
    store = MemoryStore(str(db_path))
    await store.initialize()
    yield store
    await store.close()


class TestSearchEngine:
    """Tests for CellSearchEngine."""
    
    def test_search_by_header(self, mock_sheets_client):
        """Test searching cells by column header."""
        from sheetsmith.ops.search import CellSearchEngine
        
        engine = CellSearchEngine(mock_sheets_client)
        
        criteria = SearchCriteria(header_text="Amount")
        result = engine.search("test-sheet-123", criteria)
        
        # Should find cells in the Amount column (including header row in this test)
        # The test data has 3 cells in column B: B1 (header "Amount"), B2, B3
        assert result.total_count == 3
        assert all(m.header == "Amount" for m in result.matches)
        assert all(m.col == 1 for m in result.matches)
    
    def test_search_by_formula_pattern(self, mock_sheets_client):
        """Test searching cells by formula pattern."""
        from sheetsmith.ops.search import CellSearchEngine
        
        engine = CellSearchEngine(mock_sheets_client)
        
        criteria = SearchCriteria(formula_pattern="SUM")
        result = engine.search("test-sheet-123", criteria)
        
        # Should find cells with SUM formulas
        assert result.total_count == 2
        assert all(m.formula and "SUM" in m.formula for m in result.matches)
    
    def test_search_respects_limit(self, mock_sheets_client):
        """Test that search respects the limit parameter."""
        from sheetsmith.ops.search import CellSearchEngine
        
        engine = CellSearchEngine(mock_sheets_client)
        
        criteria = SearchCriteria(formula_pattern="SUM")
        result = engine.search("test-sheet-123", criteria, limit=1)
        
        # Should only return 1 match
        assert result.total_count == 1


class TestPreviewCache:
    """Tests for PreviewCache."""
    
    def test_store_and_get(self):
        """Test storing and retrieving previews."""
        from sheetsmith.ops.models import PreviewResponse
        
        cache = PreviewCache()
        
        preview = PreviewResponse(
            preview_id="test-preview-1",
            spreadsheet_id="test-sheet-123",
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Test operation",
            changes=[],
            scope=ScopeInfo(
                total_cells=0,
                affected_sheets=[],
                affected_headers=[],
                sheet_count=0,
                requires_approval=False,
            ),
            diff_text="",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        
        preview_id = cache.store(preview)
        
        assert preview_id == "test-preview-1"
        
        retrieved = cache.get(preview_id)
        assert retrieved is not None
        assert retrieved.preview_id == preview_id
    
    def test_expired_preview_returns_none(self):
        """Test that expired previews return None."""
        from sheetsmith.ops.models import PreviewResponse
        
        cache = PreviewCache()
        
        # Create preview that's already expired
        # Note: The test creates an expired preview but the cache.store() method
        # will update expires_at to be in the future. We need to manually set it.
        preview = PreviewResponse(
            preview_id="expired-preview",
            spreadsheet_id="test-sheet-123",
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Test operation",
            changes=[],
            scope=ScopeInfo(
                total_cells=0,
                affected_sheets=[],
                affected_headers=[],
                sheet_count=0,
                requires_approval=False,
            ),
            diff_text="",
            created_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        
        # Store it directly in cache without going through store() method
        cache._cache["expired-preview"] = preview
        
        # Should return None for expired preview
        retrieved = cache.get("expired-preview")
        assert retrieved is None
    
    def test_cleanup_expired(self):
        """Test cleanup of expired previews."""
        from sheetsmith.ops.models import PreviewResponse
        
        cache = PreviewCache()
        
        # Add expired preview directly to cache
        expired = PreviewResponse(
            preview_id="expired",
            spreadsheet_id="test-sheet-123",
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Expired",
            changes=[],
            scope=ScopeInfo(
                total_cells=0,
                affected_sheets=[],
                affected_headers=[],
                sheet_count=0,
                requires_approval=False,
            ),
            diff_text="",
            created_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        cache._cache["expired"] = expired
        
        # Add valid preview using store() method
        valid = PreviewResponse(
            preview_id="valid",
            spreadsheet_id="test-sheet-123",
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Valid",
            changes=[],
            scope=ScopeInfo(
                total_cells=0,
                affected_sheets=[],
                affected_headers=[],
                sheet_count=0,
                requires_approval=False,
            ),
            diff_text="",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        cache.store(valid)
        
        assert cache.size() == 2
        
        # Cleanup
        removed = cache.cleanup_expired()
        
        assert removed == 1
        assert cache.size() == 1
        assert cache.get("valid") is not None
        assert cache.get("expired") is None


class TestPreviewGenerator:
    """Tests for PreviewGenerator."""
    
    def test_preview_replace_in_formulas(self, mock_sheets_client):
        """Test generating preview for replace in formulas operation."""
        from sheetsmith.ops.preview import PreviewGenerator
        from sheetsmith.ops.search import CellSearchEngine
        
        search_engine = CellSearchEngine(mock_sheets_client)
        generator = PreviewGenerator(mock_sheets_client, search_engine)
        
        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Replace SUM with SUMIF",
            find_pattern="SUM",
            replace_with="SUMIF",
        )
        
        preview = generator.generate_preview("test-sheet-123", operation)
        
        assert preview.preview_id is not None
        assert preview.operation_type == OperationType.REPLACE_IN_FORMULAS
        assert len(preview.changes) == 2
        assert all(c.new_formula and "SUMIF" in c.new_formula for c in preview.changes)
    
    def test_preview_scope_calculation(self, mock_sheets_client):
        """Test that preview correctly calculates scope."""
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
        
        assert preview.scope.total_cells == 2
        assert preview.scope.sheet_count == 1
        assert "Sheet1" in preview.scope.affected_sheets


class TestPreviewGenerator:
    """Tests for PreviewGenerator."""
    
    def test_preview_replace_in_formulas(self, mock_sheets_client):
        """Test generating preview for replace in formulas operation."""
        from sheetsmith.ops.preview import PreviewGenerator
        from sheetsmith.ops.search import CellSearchEngine
        
        search_engine = CellSearchEngine(mock_sheets_client)
        generator = PreviewGenerator(mock_sheets_client, search_engine)
        
        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Replace SUM with SUMIF",
            find_pattern="SUM",
            replace_with="SUMIF",
        )
        
        preview = generator.generate_preview("test-sheet-123", operation)
        
        assert preview.preview_id is not None
        assert preview.operation_type == OperationType.REPLACE_IN_FORMULAS
        assert len(preview.changes) == 2
        assert all(c.new_formula and "SUMIF" in c.new_formula for c in preview.changes)
    
    def test_preview_scope_calculation(self, mock_sheets_client):
        """Test that preview correctly calculates scope."""
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
        
        assert preview.scope.total_cells == 2
        assert preview.scope.sheet_count == 1
        assert "Sheet1" in preview.scope.affected_sheets
