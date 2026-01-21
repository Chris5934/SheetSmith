"""Tests for placeholder API endpoints."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from sheetsmith.api.routes import router


def test_placeholder_routes_registered():
    """Test that placeholder routes are properly registered."""
    route_paths = [route.path for route in router.routes]
    
    # Check all placeholder endpoints are registered
    assert "/placeholders/parse" in route_paths
    assert "/placeholders/resolve" in route_paths
    assert "/placeholders/preview" in route_paths
    assert "/placeholders/apply" in route_paths


@pytest.fixture
def mock_agent():
    """Create a mocked SheetSmith agent."""
    agent = Mock()
    agent.sheets_client = Mock()
    agent.memory_store = Mock()
    return agent


@pytest.fixture
def client(mock_agent):
    """Create a test client for the API."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    
    # Mock the get_agent function to return our mock
    with patch("sheetsmith.api.routes.get_agent", return_value=mock_agent):
        yield TestClient(app)


def test_placeholder_parse_endpoint(client):
    """Test placeholder parse endpoint works."""
    response = client.post(
        "/api/placeholders/parse",
        json={
            "formula": "={{base_damage}} * 1.5",
            "spreadsheet_id": "test-123",
            "sheet_name": "Base",
            "target_row": 2,
        },
    )
    
    # Parse should work without needing sheets access
    assert response.status_code == 200
    data = response.json()
    assert "placeholders" in data
    assert "validation" in data
    assert len(data["placeholders"]) == 1
    assert data["placeholders"][0]["name"] == "base_damage"
