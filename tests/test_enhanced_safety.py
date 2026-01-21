"""Tests for enhanced safety features: scope analyzer, audit logger, and execute_with_safety."""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from sheetsmith.engine.safety import SafetyValidator, OperationScope, SafetyCheck
from sheetsmith.engine.scope import ScopeAnalyzer
from sheetsmith.engine.audit import AuditLogger, AuditEntry
from sheetsmith.ops.engine import DeterministicOpsEngine, SafetyCheckFailedError
from sheetsmith.ops.models import Operation, OperationType, ChangeSpec


class TestOperationScope:
    """Tests for OperationScope dataclass."""
    
    def test_operation_scope_creation(self):
        """Test creating an OperationScope instance."""
        scope = OperationScope(
            total_cells=100,
            total_sheets=2,
            affected_sheets=["Sheet1", "Sheet2"],
            affected_columns=["A", "B", "C"],
            affected_rows=[1, 2, 3, 4, 5],
            estimated_duration_ms=1000.0,
            risk_level="medium"
        )
        
        assert scope.total_cells == 100
        assert scope.total_sheets == 2
        assert len(scope.affected_sheets) == 2
        assert len(scope.affected_columns) == 3
        assert len(scope.affected_rows) == 5
        assert scope.estimated_duration_ms == 1000.0
        assert scope.risk_level == "medium"


class TestEnhancedSafetyCheck:
    """Tests for enhanced SafetyCheck dataclass."""
    
    def test_safety_check_creation(self):
        """Test creating a SafetyCheck instance."""
        scope = OperationScope(
            total_cells=50,
            total_sheets=1,
            affected_sheets=["Sheet1"],
            affected_columns=["A", "B"],
            affected_rows=[1, 2, 3],
            estimated_duration_ms=500.0,
            risk_level="low"
        )
        
        check = SafetyCheck(
            allowed=True,
            warnings=["Minor warning"],
            errors=[],
            scope=scope,
            requires_confirmation=False,
            requires_preview=True
        )
        
        assert check.allowed is True
        assert len(check.warnings) == 1
        assert len(check.errors) == 0
        assert check.requires_confirmation is False
        assert check.requires_preview is True
        assert check.scope.total_cells == 50


class TestSafetyValidatorEnhanced:
    """Tests for enhanced SafetyValidator methods."""
    
    def test_validate_operation_with_scope_success(self):
        """Test validation with scope that passes all checks."""
        validator = SafetyValidator()
        
        scope = OperationScope(
            total_cells=50,
            total_sheets=2,
            affected_sheets=["Sheet1", "Sheet2"],
            affected_columns=["A", "B"],
            affected_rows=[1, 2, 3],
            estimated_duration_ms=500.0,
            risk_level="low"
        )
        
        check = validator.validate_operation_with_scope(
            "replace_in_formulas", scope, dry_run=False
        )
        
        assert check.allowed is True
        assert len(check.errors) == 0
        assert check.scope == scope
    
    def test_validate_operation_with_scope_cells_exceeded(self):
        """Test validation fails when cells limit exceeded."""
        validator = SafetyValidator()
        
        scope = OperationScope(
            total_cells=1000,  # Exceeds default limit of 500
            total_sheets=2,
            affected_sheets=["Sheet1", "Sheet2"],
            affected_columns=["A", "B"],
            affected_rows=list(range(1, 501)),
            estimated_duration_ms=10000.0,
            risk_level="high"
        )
        
        check = validator.validate_operation_with_scope(
            "replace_in_formulas", scope, dry_run=False
        )
        
        assert check.allowed is False
        assert len(check.errors) > 0
        assert "exceeds limit" in check.errors[0]
        assert "1000" in check.errors[0]
    
    def test_validate_operation_with_scope_sheets_exceeded(self):
        """Test validation fails when sheets limit exceeded."""
        validator = SafetyValidator()
        
        scope = OperationScope(
            total_cells=50,
            total_sheets=50,  # Exceeds default limit of 40
            affected_sheets=[f"Sheet{i}" for i in range(50)],
            affected_columns=["A"],
            affected_rows=[1],
            estimated_duration_ms=500.0,
            risk_level="high"
        )
        
        check = validator.validate_operation_with_scope(
            "replace_in_formulas", scope, dry_run=False
        )
        
        assert check.allowed is False
        assert len(check.errors) > 0
        assert "sheets" in check.errors[0].lower()
    
    def test_validate_operation_with_scope_warning_large_op(self):
        """Test that large operations generate warnings."""
        validator = SafetyValidator()
        
        scope = OperationScope(
            total_cells=15,  # Above preview threshold of 10
            total_sheets=1,
            affected_sheets=["Sheet1"],
            affected_columns=["A"],
            affected_rows=list(range(1, 16)),
            estimated_duration_ms=150.0,
            risk_level="low"
        )
        
        check = validator.validate_operation_with_scope(
            "replace_in_formulas", scope, dry_run=False
        )
        
        assert check.allowed is True
        assert len(check.warnings) > 0
        assert check.requires_preview is True
    
    def test_assess_risk_levels(self):
        """Test risk assessment for different scopes."""
        validator = SafetyValidator()
        
        # Low risk
        low_scope = OperationScope(
            total_cells=10, total_sheets=1, affected_sheets=["Sheet1"],
            affected_columns=["A"], affected_rows=[1], estimated_duration_ms=100.0,
            risk_level=""
        )
        risk = validator._assess_risk(low_scope)
        assert risk == "low"
        
        # Medium risk (> 50% of max cells)
        medium_scope = OperationScope(
            total_cells=300, total_sheets=1, affected_sheets=["Sheet1"],
            affected_columns=["A"], affected_rows=list(range(300)),
            estimated_duration_ms=3000.0, risk_level=""
        )
        risk = validator._assess_risk(medium_scope)
        assert risk == "medium"
        
        # High risk (> 80% of max cells)
        high_scope = OperationScope(
            total_cells=450, total_sheets=1, affected_sheets=["Sheet1"],
            affected_columns=["A"], affected_rows=list(range(450)),
            estimated_duration_ms=4500.0, risk_level=""
        )
        risk = validator._assess_risk(high_scope)
        assert risk == "high"
    
    def test_validate_formula_length(self):
        """Test formula length validation."""
        validator = SafetyValidator()
        
        # Short formula (should pass)
        valid, error = validator.validate_formula_length("=SUM(A1:A10)")
        assert valid is True
        assert error is None
        
        # Long formula (should fail)
        long_formula = "=" + "A" * 60000
        valid, error = validator.validate_formula_length(long_formula)
        assert valid is False
        assert error is not None
        assert "exceeds limit" in error


class TestScopeAnalyzer:
    """Tests for ScopeAnalyzer class."""
    
    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked Google Sheets client."""
        return Mock()
    
    @pytest.fixture
    def analyzer(self, mock_sheets_client):
        """Create a ScopeAnalyzer instance."""
        return ScopeAnalyzer(mock_sheets_client)
    
    def test_analyze_from_empty_changes(self, analyzer):
        """Test analysis with no changes."""
        scope = analyzer.analyze_from_changes([], "test_op")
        
        assert scope.total_cells == 0
        assert scope.total_sheets == 0
        assert len(scope.affected_sheets) == 0
        assert scope.risk_level == "low"
    
    def test_analyze_from_single_sheet_changes(self, analyzer):
        """Test analysis with changes in single sheet."""
        changes = [
            ChangeSpec(
                sheet_name="Sheet1",
                cell="A1",
                old_formula="=SUM(B1:B10)",
                new_formula="=SUMIF(B1:B10, >0)",
            ),
            ChangeSpec(
                sheet_name="Sheet1",
                cell="A2",
                old_formula="=SUM(B2:B11)",
                new_formula="=SUMIF(B2:B11, >0)",
            ),
            ChangeSpec(
                sheet_name="Sheet1",
                cell="B5",
                old_value="100",
                new_value="200",
            ),
        ]
        
        scope = analyzer.analyze_from_changes(changes, "replace_in_formulas")
        
        assert scope.total_cells == 3
        assert scope.total_sheets == 1
        assert "Sheet1" in scope.affected_sheets
        assert "A" in scope.affected_columns
        assert "B" in scope.affected_columns
        assert 1 in scope.affected_rows
        assert 2 in scope.affected_rows
        assert 5 in scope.affected_rows
        assert scope.estimated_duration_ms == 30.0  # 3 cells * 10ms
    
    def test_analyze_from_multi_sheet_changes(self, analyzer):
        """Test analysis with changes across multiple sheets."""
        changes = [
            ChangeSpec(sheet_name="Sheet1", cell="A1", old_value="1", new_value="2"),
            ChangeSpec(sheet_name="Sheet2", cell="B2", old_value="2", new_value="3"),
            ChangeSpec(sheet_name="Sheet3", cell="C3", old_value="3", new_value="4"),
        ]
        
        scope = analyzer.analyze_from_changes(changes, "set_values")
        
        assert scope.total_cells == 3
        assert scope.total_sheets == 3
        assert set(scope.affected_sheets) == {"Sheet1", "Sheet2", "Sheet3"}
    
    def test_analyze_risk_assessment(self, analyzer):
        """Test risk level assessment based on change volume."""
        # Low risk (< 100 cells)
        low_changes = [
            ChangeSpec(sheet_name="Sheet1", cell=f"A{i}", old_value=str(i), new_value=str(i+1))
            for i in range(1, 51)
        ]
        low_scope = analyzer.analyze_from_changes(low_changes, "test")
        assert low_scope.risk_level == "low"
        
        # Medium risk (100-300 cells)
        medium_changes = [
            ChangeSpec(sheet_name="Sheet1", cell=f"A{i}", old_value=str(i), new_value=str(i+1))
            for i in range(1, 151)
        ]
        medium_scope = analyzer.analyze_from_changes(medium_changes, "test")
        assert medium_scope.risk_level == "medium"
        
        # High risk (> 300 cells)
        high_changes = [
            ChangeSpec(sheet_name="Sheet1", cell=f"A{i}", old_value=str(i), new_value=str(i+1))
            for i in range(1, 351)
        ]
        high_scope = analyzer.analyze_from_changes(high_changes, "test")
        assert high_scope.risk_level == "high"


class TestAuditLogger:
    """Tests for AuditLogger class."""
    
    @pytest_asyncio.fixture
    async def memory_store(self, tmp_path):
        """Create a test memory store."""
        from sheetsmith.memory import MemoryStore
        db_path = tmp_path / "test_audit.db"
        store = MemoryStore(db_path)
        await store.initialize()
        yield store
        await store.close()
    
    def test_audit_logger_init(self):
        """Test AuditLogger initialization."""
        logger = AuditLogger(None)
        assert logger.memory_store is None
    
    @pytest.mark.asyncio
    async def test_log_operation_success(self, tmp_path):
        """Test logging a successful operation."""
        from sheetsmith.memory import MemoryStore
        
        # Create memory store inline
        db_path = tmp_path / "test_audit.db"
        store = MemoryStore(db_path)
        await store.initialize()
        
        audit_logger = AuditLogger(store)
        
        entry = AuditEntry(
            id="test-123",
            timestamp=datetime.utcnow().isoformat(),
            operation_type="replace_in_formulas",
            spreadsheet_id="sheet-456",
            user="test_user",
            preview_id="preview-789",
            scope={"total_cells": 10, "total_sheets": 1},
            status="success",
            changes_applied=10,
            errors=[],
            duration_ms=1234.5
        )
        
        await audit_logger.log_operation(entry)
        
        # Verify log was stored
        logs = await audit_logger.get_recent_operations(limit=10)
        assert len(logs) > 0
        assert logs[0].id == "test-123"
        assert logs[0].operation_type == "replace_in_formulas"
        assert logs[0].status == "success"
        assert logs[0].changes_applied == 10
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_log_operation_failure(self, tmp_path):
        """Test logging a failed operation."""
        from sheetsmith.memory import MemoryStore
        
        db_path = tmp_path / "test_audit.db"
        store = MemoryStore(db_path)
        await store.initialize()
        
        audit_logger = AuditLogger(store)
        
        entry = AuditEntry(
            id="test-456",
            timestamp=datetime.utcnow().isoformat(),
            operation_type="set_values",
            spreadsheet_id="sheet-789",
            user="test_user",
            preview_id=None,
            scope={"total_cells": 100, "total_sheets": 2},
            status="failed",
            changes_applied=0,
            errors=["Operation exceeded cell limit"],
            duration_ms=100.0
        )
        
        await audit_logger.log_operation(entry)
        
        # Verify log was stored
        logs = await audit_logger.get_recent_operations(limit=10)
        assert any(log.id == "test-456" for log in logs)
        failed_log = next(log for log in logs if log.id == "test-456")
        assert failed_log.status == "failed"
        assert len(failed_log.errors) > 0
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_get_recent_operations_filtered(self, tmp_path):
        """Test retrieving operations filtered by spreadsheet."""
        from sheetsmith.memory import MemoryStore
        
        db_path = tmp_path / "test_audit.db"
        store = MemoryStore(db_path)
        await store.initialize()
        
        audit_logger = AuditLogger(store)
        
        # Log operations for different spreadsheets
        for i in range(5):
            entry = AuditEntry(
                id=f"test-{i}",
                timestamp=datetime.utcnow().isoformat(),
                operation_type="replace_in_formulas",
                spreadsheet_id=f"sheet-{i % 2}",  # Alternate between 2 sheets
                user="test_user",
                preview_id=None,
                scope={"total_cells": 10},
                status="success",
                changes_applied=10,
                errors=[],
                duration_ms=100.0
            )
            await audit_logger.log_operation(entry)
        
        # Get operations for specific spreadsheet
        logs = await audit_logger.get_recent_operations(
            limit=10, spreadsheet_id="sheet-0"
        )
        
        # Should only get operations for sheet-0
        assert all(log.spreadsheet_id == "sheet-0" for log in logs)
        
        await store.close()




class TestExecuteWithSafety:
    """Tests for DeterministicOpsEngine.execute_with_safety method."""
    
    def create_mock_sheets_client(self):
        """Create a mocked Google Sheets client."""
        client = Mock()
        client.get_spreadsheet_info = Mock(return_value={
            "id": "test-123",
            "title": "Test Sheet",
            "sheets": [{"title": "Sheet1", "id": 0}]
        })
        return client
    
    @pytest.mark.asyncio
    async def test_execute_with_safety_passes(self, tmp_path):
        """Test execute_with_safety with operation that passes safety checks."""
        from sheetsmith.memory import MemoryStore
        
        mock_sheets_client = self.create_mock_sheets_client()
        
        # Create memory store inline
        db_path = tmp_path / "test_ops.db"
        store = MemoryStore(db_path)
        await store.initialize()
        
        ops_engine = DeterministicOpsEngine(mock_sheets_client, store)
        
        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Test operation",
            find_pattern="SUM",
            replace_with="SUMIF",
        )
        
        # Mock the generate_preview to return a small preview
        with patch.object(ops_engine, 'generate_preview') as mock_preview:
            mock_preview.return_value = Mock(
                preview_id="test-preview",
                changes=[
                    ChangeSpec(
                        sheet_name="Sheet1",
                        cell="A1",
                        old_formula="=SUM(B1:B10)",
                        new_formula="=SUMIF(B1:B10, >0)",
                    )
                ],
                operation_type=OperationType.REPLACE_IN_FORMULAS,
                scope=Mock(
                    total_cells=1,
                    affected_sheets=["Sheet1"],
                    affected_headers=[],
                    sheet_count=1,
                    requires_approval=False
                )
            )
            
            preview = await ops_engine.execute_with_safety(
                "test-sheet-123", operation, require_preview=True
            )
            
            assert preview is not None
            assert preview.preview_id == "test-preview"
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_execute_with_safety_blocked(self, tmp_path):
        """Test execute_with_safety blocks operation exceeding limits."""
        from sheetsmith.memory import MemoryStore
        
        mock_sheets_client = self.create_mock_sheets_client()
        
        # Create memory store inline
        db_path = tmp_path / "test_ops.db"
        store = MemoryStore(db_path)
        await store.initialize()
        
        ops_engine = DeterministicOpsEngine(mock_sheets_client, store)
        
        operation = Operation(
            operation_type=OperationType.REPLACE_IN_FORMULAS,
            description="Large operation",
            find_pattern="SUM",
            replace_with="SUMIF",
        )
        
        # Mock generate_preview to return a large preview
        with patch.object(ops_engine, 'generate_preview') as mock_preview:
            # Create many changes to exceed limit
            large_changes = [
                ChangeSpec(
                    sheet_name="Sheet1",
                    cell=f"A{i}",
                    old_formula=f"=SUM(B{i}:B{i+10})",
                    new_formula=f"=SUMIF(B{i}:B{i+10}, >0)",
                )
                for i in range(1, 600)  # Exceeds 500 cell limit
            ]
            
            mock_preview.return_value = Mock(
                preview_id="test-preview",
                changes=large_changes,
                operation_type=OperationType.REPLACE_IN_FORMULAS,
                scope=Mock(
                    total_cells=599,
                    affected_sheets=["Sheet1"],
                    affected_headers=[],
                    sheet_count=1,
                    requires_approval=True
                )
            )
            
            # Should raise SafetyCheckFailedError
            with pytest.raises(SafetyCheckFailedError) as exc_info:
                await ops_engine.execute_with_safety(
                    "test-sheet-123", operation, require_preview=True
                )
            
            assert "blocked by safety checks" in str(exc_info.value).lower()
        
        await store.close()
