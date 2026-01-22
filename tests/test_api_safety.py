"""Integration tests for safety API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from sheetsmith.api.app import create_app
from sheetsmith.ops.models import Operation, OperationType, SearchCriteria


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_ops_engine():
    """Create a mocked ops engine."""
    engine = Mock()
    engine.generate_preview = Mock()
    engine.apply_changes = AsyncMock()
    engine.sheets_client = Mock()
    return engine


class TestSafetyAPIEndpoints:
    """Tests for safety-related API endpoints."""

    def test_config_limits_endpoint(self, client):
        """Test that config limits endpoint returns expected values."""
        response = client.get("/api/config/limits")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "safety_limits" in data
        assert "max_cells_per_operation" in data["safety_limits"]
        assert "max_sheets_per_operation" in data["safety_limits"]
        assert "max_formula_length" in data["safety_limits"]
        assert "require_preview_above_cells" in data["safety_limits"]
        
        # Verify values are reasonable
        assert data["safety_limits"]["max_cells_per_operation"] > 0
        assert data["safety_limits"]["max_sheets_per_operation"] > 0

    @patch("sheetsmith.api.routes.get_ops_engine")
    def test_preflight_endpoint_basic(self, mock_get_engine, client):
        """Test preflight endpoint with basic operation."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.sheets_client = Mock()
        mock_get_engine.return_value = mock_engine
        
        # Make request
        request_data = {
            "spreadsheet_id": "test-123",
            "operation": {
                "operation_type": "replace_in_formulas",
                "description": "Test operation",
                "find_pattern": "SUM",
                "replace_with": "SUMIF",
            }
        }
        
        response = client.post("/api/ops/preflight", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "passed" in data
        assert "warnings" in data
        assert "errors" in data
        assert "limit_breaches" in data
        assert "ambiguities" in data
        assert "estimated_scope" in data

    @patch("sheetsmith.api.routes.get_ops_engine")
    def test_audit_mappings_endpoint(self, mock_get_engine, client):
        """Test audit mappings endpoint."""
        # Setup mock
        mock_engine = Mock()
        mock_engine.sheets_client = Mock()
        mock_get_engine.return_value = mock_engine
        
        # Make request
        response = client.post(
            "/api/ops/audit/mappings",
            params={"spreadsheet_id": "test-123"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "spreadsheet_id" in data
        assert "mappings_checked" in data
        assert "valid_mappings" in data
        assert "invalid_mappings" in data
        assert "warnings" in data
        assert "recommendations" in data

    def test_health_endpoint_includes_safety_config(self, client):
        """Test that health endpoint is accessible."""
        response = client.get("/api/health")
        
        # Should return OK even without full setup
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"


class TestDryRunSupport:
    """Tests for dry-run functionality in API."""

    @patch("sheetsmith.api.routes.get_ops_engine")
    def test_preview_with_dry_run(self, mock_get_engine, client):
        """Test preview endpoint with dry_run flag."""
        from sheetsmith.ops.models import PreviewResponse, ScopeInfo
        from datetime import datetime, timedelta, timezone
        
        # Setup mock
        mock_engine = Mock()
        mock_preview = PreviewResponse(
            preview_id="test-preview-123",
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
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        mock_engine.generate_preview.return_value = mock_preview
        mock_get_engine.return_value = mock_engine
        
        # Make request with dry_run
        request_data = {
            "spreadsheet_id": "test-sheet-123",
            "operation": {
                "operation_type": "replace_in_formulas",
                "description": "Test operation",
                "find_pattern": "SUM",
                "replace_with": "SUMIF",
            },
            "dry_run": True,
        }
        
        response = client.post("/api/ops/preview", json=request_data)
        
        # Verify response includes dry_run flag
        assert response.status_code == 200
        data = response.json()
        assert "dry_run" in data
        assert data["dry_run"] is True

    @patch("sheetsmith.api.routes.get_ops_engine")
    def test_apply_with_dry_run(self, mock_get_engine, client):
        """Test apply endpoint with dry_run flag."""
        from sheetsmith.ops.models import ApplyResponse
        from datetime import datetime, timezone
        
        # Setup mock
        mock_engine = Mock()
        mock_result = ApplyResponse(
            success=True,
            preview_id="test-preview-123",
            spreadsheet_id="test-sheet-123",
            cells_updated=10,
            errors=[],
            applied_at=datetime.now(timezone.utc),
        )
        mock_engine.apply_changes = AsyncMock(return_value=mock_result)
        mock_get_engine.return_value = mock_engine
        
        # Make request with dry_run
        request_data = {
            "preview_id": "test-preview-123",
            "confirmation": True,
            "dry_run": True,
        }
        
        response = client.post("/api/ops/apply", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "dry_run" in data
        assert data["dry_run"] is True
        
        # Verify dry_run was passed to engine
        mock_engine.apply_changes.assert_called_once()
        call_kwargs = mock_engine.apply_changes.call_args[1]
        assert call_kwargs.get("dry_run") is True
