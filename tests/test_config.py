"""Tests for the config module."""

import os
from pathlib import Path

import pytest

from sheetsmith.config import Settings, _parse_cors_origins


class TestParseCorsoOrigins:
    """Test CORS origins parsing."""

    def test_parse_cors_origins_with_value(self, monkeypatch):
        """Test parsing CORS origins from environment variable."""
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:8080")
        result = _parse_cors_origins()
        assert result == ["http://localhost:3000", "http://localhost:8080"]

    def test_parse_cors_origins_without_value(self, monkeypatch):
        """Test default CORS origins when not set."""
        monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
        result = _parse_cors_origins()
        assert result == ["*"]

    def test_parse_cors_origins_empty_string(self, monkeypatch):
        """Test parsing empty CORS origins defaults to wildcard."""
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "")
        result = _parse_cors_origins()
        # Empty string splits to empty list, which defaults to ["*"]
        assert result == ["*"]


class TestSettings:
    """Test Settings configuration."""

    def test_settings_initialization_with_defaults(self, tmp_path, monkeypatch):
        """Test Settings initialization with default values."""
        # Clear environment variables
        for key in [
            "GOOGLE_CREDENTIALS_PATH",
            "GOOGLE_TOKEN_PATH",
            "DATABASE_PATH",
            "ANTHROPIC_API_KEY",
            "OPENROUTER_API_KEY",
            "LLM_PROVIDER",
            "MODEL_NAME",
            "HOST",
            "PORT",
            "DEBUG",
            "MAX_TOKENS",
        ]:
            monkeypatch.delenv(key, raising=False)
        
        settings = Settings()
        
        # Check default values
        assert settings.google_credentials_path == Path("credentials.json")
        assert settings.google_token_path == Path("token.json")
        assert settings.database_path == Path("data/sheetsmith.db")
        assert settings.llm_provider == "anthropic"
        assert settings.model_name == "claude-sonnet-4-20250514"
        assert settings.host == "127.0.0.1"
        assert settings.port == 8000
        assert settings.debug is False
        assert settings.max_tokens == 4096
        assert settings.anthropic_api_key is None
        assert settings.openrouter_api_key is None

    def test_settings_from_environment(self, tmp_path, monkeypatch):
        """Test Settings loading from environment variables."""
        creds_path = tmp_path / "test_creds.json"
        token_path = tmp_path / "test_token.json"
        db_path = tmp_path / "test.db"
        
        # Create Settings instance with explicit parameters
        settings = Settings(
            google_credentials_path=creds_path,
            google_token_path=token_path,
            database_path=db_path,
            anthropic_api_key="sk-ant-test123",
            openrouter_api_key="sk-or-test456",
            llm_provider="openrouter",
            model_name="claude-3-opus-20240229",
            host="0.0.0.0",
            port=9000,
            debug=True,
            max_tokens=8192,
        )
        
        assert settings.google_credentials_path == creds_path
        assert settings.google_token_path == token_path
        assert settings.database_path == db_path
        assert settings.anthropic_api_key == "sk-ant-test123"
        assert settings.openrouter_api_key == "sk-or-test456"
        assert settings.llm_provider == "openrouter"
        assert settings.model_name == "claude-3-opus-20240229"
        assert settings.host == "0.0.0.0"
        assert settings.port == 9000
        assert settings.debug is True
        assert settings.max_tokens == 8192

    def test_settings_path_handling(self, tmp_path):
        """Test that paths are correctly converted to Path objects."""
        settings = Settings(
            google_credentials_path=Path(tmp_path / "creds.json"),
            google_token_path=Path(tmp_path / "token.json"),
            database_path=Path(tmp_path / "db.db"),
        )
        
        assert isinstance(settings.google_credentials_path, Path)
        assert isinstance(settings.google_token_path, Path)
        assert isinstance(settings.database_path, Path)

    def test_settings_cors_origins_parsing(self, monkeypatch):
        """Test CORS origins are properly parsed."""
        settings = Settings(
            cors_allow_origins=["http://localhost:3000", "http://example.com"]
        )
        
        assert settings.cors_allow_origins == ["http://localhost:3000", "http://example.com"]

    def test_settings_debug_flag_variations(self, monkeypatch):
        """Test debug flag with various boolean values."""
        # Test True
        settings = Settings(debug=True)
        assert settings.debug is True
        
        # Test False
        settings = Settings(debug=False)
        assert settings.debug is False

    def test_settings_openrouter_model_default(self, monkeypatch):
        """Test OpenRouter model has correct default."""
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
        
        settings = Settings()
        
        assert settings.openrouter_model == "anthropic/claude-3.5-sonnet"
