"""Tests for mode router and operation modes."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from sheetsmith.modes import (
    OperationMode,
    OperationRequest,
    DeterministicReplaceRequest,
    SetValueRequest,
    AIAssistRequest,
    ModeSwitchRequest,
)
from sheetsmith.modes.router import ModeRouter
from sheetsmith.ops import DeterministicOpsEngine
from sheetsmith.ops.models import (
    Operation,
    OperationType,
    PreviewResponse,
    ChangeSpec,
    ScopeInfo,
)


@pytest.fixture
def mock_ops_engine():
    """Create a mocked ops engine."""
    engine = Mock(spec=DeterministicOpsEngine)
    
    # Mock preview method
    async def mock_preview(spreadsheet_id, operation):
        from datetime import datetime, timedelta
        return PreviewResponse(
            preview_id="preview-123",
            spreadsheet_id=spreadsheet_id,
            operation_type=operation.operation_type,
            description=operation.description,
            changes=[
                ChangeSpec(
                    sheet_name="Sheet1",
                    cell="B2",
                    old_value="old",
                    new_value="new",
                    header="Test Header",
                )
            ],
            scope=ScopeInfo(
                total_cells=1,
                affected_sheets=["Sheet1"],
                affected_headers=["Test Header"],
                sheet_count=1,
                requires_approval=True,
            ),
            diff_text="- old\n+ new",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
    
    engine.preview = AsyncMock(side_effect=mock_preview)
    return engine


@pytest.fixture
def mode_router(mock_ops_engine):
    """Create a mode router with mocked dependencies."""
    return ModeRouter(ops_engine=mock_ops_engine)


class TestOperationMode:
    """Tests for OperationMode enum."""
    
    def test_operation_mode_values(self):
        """Test operation mode enum values."""
        assert OperationMode.DETERMINISTIC == "deterministic"
        assert OperationMode.AI_ASSIST == "ai_assist"
    
    def test_operation_mode_string_conversion(self):
        """Test that modes have correct values."""
        assert OperationMode.DETERMINISTIC.value == "deterministic"


class TestOperationRequest:
    """Tests for OperationRequest model."""
    
    def test_operation_request_defaults(self):
        """Test default values in operation request."""
        request = OperationRequest(
            operation_type="replace_in_formulas",
            spreadsheet_id="test-123",
        )
        assert request.mode == OperationMode.DETERMINISTIC
        assert request.parameters == {}
    
    def test_operation_request_with_parameters(self):
        """Test operation request with custom parameters."""
        request = OperationRequest(
            mode=OperationMode.AI_ASSIST,
            operation_type="replace_in_formulas",
            spreadsheet_id="test-123",
            parameters={"header_text": "Test", "find": "old", "replace": "new"},
        )
        assert request.mode == OperationMode.AI_ASSIST
        assert request.parameters["header_text"] == "Test"


class TestDeterministicReplaceRequest:
    """Tests for DeterministicReplaceRequest model."""
    
    def test_deterministic_replace_request_minimal(self):
        """Test minimal deterministic replace request."""
        request = DeterministicReplaceRequest(
            spreadsheet_id="test-123",
            header_text="Test Header",
            find="old",
            replace="new",
        )
        assert request.spreadsheet_id == "test-123"
        assert request.header_text == "Test Header"
        assert request.find == "old"
        assert request.replace == "new"
        assert request.sheet_names is None
        assert request.case_sensitive is False
        assert request.is_regex is False
    
    def test_deterministic_replace_request_with_sheets(self):
        """Test deterministic replace request with specific sheets."""
        request = DeterministicReplaceRequest(
            spreadsheet_id="test-123",
            header_text="Test Header",
            find="old",
            replace="new",
            sheet_names=["Sheet1", "Sheet2"],
            case_sensitive=True,
        )
        assert request.sheet_names == ["Sheet1", "Sheet2"]
        assert request.case_sensitive is True


class TestSetValueRequest:
    """Tests for SetValueRequest model."""
    
    def test_set_value_request(self):
        """Test set value request."""
        request = SetValueRequest(
            spreadsheet_id="test-123",
            sheet_name="Sheet1",
            header="Amount",
            row_label="Item1",
            value=100,
        )
        assert request.spreadsheet_id == "test-123"
        assert request.sheet_name == "Sheet1"
        assert request.header == "Amount"
        assert request.row_label == "Item1"
        assert request.value == 100


class TestModeRouter:
    """Tests for ModeRouter class."""
    
    @pytest.mark.asyncio
    async def test_route_deterministic_replace(self, mode_router):
        """Test routing a deterministic replace operation."""
        request = OperationRequest(
            mode=OperationMode.DETERMINISTIC,
            operation_type="replace_in_formulas",
            spreadsheet_id="test-123",
            parameters={
                "header_text": "Test Header",
                "find": "old",
                "replace": "new",
            },
        )
        
        result = await mode_router.route_operation(request)
        
        assert result.preview_id == "preview-123"
        assert result.spreadsheet_id == "test-123"
        assert len(result.changes) == 1
        assert result.changes[0].header == "Test Header"
    
    @pytest.mark.asyncio
    async def test_route_deterministic_set_value(self, mode_router):
        """Test routing a deterministic set value operation."""
        request = OperationRequest(
            mode=OperationMode.DETERMINISTIC,
            operation_type="set_value_by_header",
            spreadsheet_id="test-123",
            parameters={
                "sheet_name": "Sheet1",
                "header": "Amount",
                "row_label": "Item1",
                "value": 200,
            },
        )
        
        result = await mode_router.route_operation(request)
        
        assert result.preview_id == "preview-123"
        assert result.spreadsheet_id == "test-123"
    
    @pytest.mark.asyncio
    async def test_validate_deterministic_params_replace(self, mode_router):
        """Test parameter validation for replace operation."""
        # Valid request
        request = OperationRequest(
            operation_type="replace_in_formulas",
            spreadsheet_id="test-123",
            parameters={
                "header_text": "Test",
                "find": "old",
                "replace": "new",
            },
        )
        assert mode_router._validate_deterministic_params(request) is True
        
        # Invalid request - missing find
        request = OperationRequest(
            operation_type="replace_in_formulas",
            spreadsheet_id="test-123",
            parameters={
                "header_text": "Test",
                "replace": "new",
            },
        )
        assert mode_router._validate_deterministic_params(request) is False
    
    @pytest.mark.asyncio
    async def test_validate_deterministic_params_set_value(self, mode_router):
        """Test parameter validation for set value operation."""
        # Valid request
        request = OperationRequest(
            operation_type="set_value_by_header",
            spreadsheet_id="test-123",
            parameters={
                "sheet_name": "Sheet1",
                "header": "Amount",
                "row_label": "Item1",
                "value": 100,
            },
        )
        assert mode_router._validate_deterministic_params(request) is True
        
        # Invalid request - missing header
        request = OperationRequest(
            operation_type="set_value_by_header",
            spreadsheet_id="test-123",
            parameters={
                "sheet_name": "Sheet1",
                "row_label": "Item1",
                "value": 100,
            },
        )
        assert mode_router._validate_deterministic_params(request) is False
    
    @pytest.mark.asyncio
    async def test_route_ai_assist_not_implemented(self, mode_router):
        """Test that AI assist mode raises error when no AI agent."""
        request = OperationRequest(
            mode=OperationMode.AI_ASSIST,
            operation_type="replace_in_formulas",
            spreadsheet_id="test-123",
            parameters={"request": "Update all values"},
        )
        
        with pytest.raises(ValueError, match="AI agent not available"):
            await mode_router.route_operation(request)
    
    @pytest.mark.asyncio
    async def test_invalid_parameters_raise_error(self, mode_router):
        """Test that invalid parameters raise an error."""
        request = OperationRequest(
            mode=OperationMode.DETERMINISTIC,
            operation_type="replace_in_formulas",
            spreadsheet_id="test-123",
            parameters={
                # Missing required parameters
                "header_text": "Test",
            },
        )
        
        with pytest.raises(ValueError, match="ambiguous or incomplete"):
            await mode_router.route_operation(request)


class TestModeSwitchRequest:
    """Tests for ModeSwitchRequest model."""
    
    def test_mode_switch_request(self):
        """Test mode switch request."""
        request = ModeSwitchRequest(
            from_mode=OperationMode.DETERMINISTIC,
            to_mode=OperationMode.AI_ASSIST,
            operation_data={"test": "data"},
        )
        assert request.from_mode == OperationMode.DETERMINISTIC
        assert request.to_mode == OperationMode.AI_ASSIST
        assert request.operation_data == {"test": "data"}
