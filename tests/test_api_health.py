"""Tests for the health check API endpoint."""

from unittest.mock import patch, Mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create a test client without lifespan (to avoid agent initialization)."""
    # Create app without lifespan to avoid initializing the agent
    from fastapi import FastAPI
    from sheetsmith.api.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api")

    return TestClient(app)


class TestHealthEndpoint:
    """Test the /api/health endpoint."""

    def test_health_check_returns_ok_status(self, test_client):
        """Test that health check returns status 'ok'."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "sheetsmith"

    def test_health_check_includes_llm_provider_info(self, test_client):
        """Test that health check includes LLM provider information."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "config" in data
        assert "llm_provider" in data["config"]
        assert "model_name" in data["config"]

    def test_health_check_shows_key_presence_without_secrets(self, test_client):
        """Test that health check shows key presence without exposing actual keys."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        config = data["config"]

        # Should have boolean flags for key presence
        assert "anthropic_key_present" in config
        assert "openrouter_key_present" in config
        assert isinstance(config["anthropic_key_present"], bool)
        assert isinstance(config["openrouter_key_present"], bool)

        # Should NOT contain actual API keys
        response_text = response.text
        assert "sk-ant-" not in response_text
        assert "sk-or-" not in response_text

    def test_health_check_includes_google_credentials_status(self, test_client):
        """Test that health check includes Google credentials configuration status."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "google_credentials_configured" in data["config"]
        assert isinstance(data["config"]["google_credentials_configured"], bool)

    @patch("sheetsmith.config.settings")
    def test_health_check_with_anthropic_provider(self, mock_settings, test_client):
        """Test health check when using Anthropic provider."""
        # Create a mock path object
        mock_path = Mock()
        mock_path.exists = Mock(return_value=False)

        mock_settings.llm_provider = "anthropic"
        mock_settings.model_name = "claude-sonnet-4-20250514"
        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.openrouter_api_key = None
        mock_settings.google_credentials_path = mock_path

        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["llm_provider"] == "anthropic"
        assert data["config"]["anthropic_key_present"] is True
        assert data["config"]["openrouter_key_present"] is False

    @patch("sheetsmith.config.settings")
    def test_health_check_with_openrouter_provider(self, mock_settings, test_client):
        """Test health check when using OpenRouter provider."""
        # Create a mock path object
        mock_path = Mock()
        mock_path.exists = Mock(return_value=True)

        mock_settings.llm_provider = "openrouter"
        mock_settings.model_name = "anthropic/claude-3.5-sonnet"
        mock_settings.anthropic_api_key = None
        mock_settings.openrouter_api_key = "sk-or-test"
        mock_settings.google_credentials_path = mock_path

        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["llm_provider"] == "openrouter"
        assert data["config"]["openrouter_key_present"] is True
        assert data["config"]["google_credentials_configured"] is True

    def test_health_check_response_structure(self, test_client):
        """Test that health check response has expected structure."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        # Top-level keys
        assert "status" in data
        assert "service" in data
        assert "config" in data

        # Config keys
        config = data["config"]
        assert "llm_provider" in config
        assert "model_name" in config
        assert "anthropic_key_present" in config
        assert "openrouter_key_present" in config
        assert "google_credentials_configured" in config
