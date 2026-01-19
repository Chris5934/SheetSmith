"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path
from unittest.mock import Mock
from typing import AsyncGenerator

import pytest

from sheetsmith.config import Settings
from sheetsmith.sheets import GoogleSheetsClient
from sheetsmith.memory import MemoryStore
from sheetsmith.llm import AnthropicClient


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Create settings with test values."""
    # Create temporary files for credentials
    creds_file = tmp_path / "credentials.json"
    token_file = tmp_path / "token.json"
    db_file = tmp_path / "test.db"

    creds_file.write_text('{"installed": {"client_id": "test"}}')
    token_file.write_text('{"token": "test"}')

    # Override environment variables for this test
    os.environ["GOOGLE_CREDENTIALS_PATH"] = str(creds_file)
    os.environ["GOOGLE_TOKEN_PATH"] = str(token_file)
    os.environ["DATABASE_PATH"] = str(db_file)
    os.environ["ANTHROPIC_API_KEY"] = "test-key-123"
    os.environ["LLM_PROVIDER"] = "anthropic"
    os.environ["MODEL_NAME"] = "claude-sonnet-4-20250514"

    # Create fresh Settings instance
    settings = Settings(
        google_credentials_path=creds_file,
        google_token_path=token_file,
        database_path=db_file,
        anthropic_api_key="test-key-123",
        llm_provider="anthropic",
        model_name="claude-sonnet-4-20250514",
        host="127.0.0.1",
        port=8000,
        debug=False,
        cors_allow_origins=["*"],
        max_tokens=4096,
    )

    return settings


@pytest.fixture
def mock_sheets_client() -> Mock:
    """Create a mocked Google Sheets client."""
    client = Mock(spec=GoogleSheetsClient)

    # Mock common methods
    client.get_spreadsheet_info = Mock(
        return_value={
            "spreadsheet_id": "test-sheet-123",
            "title": "Test Sheet",
            "sheets": [{"title": "Sheet1", "id": 0}],
        }
    )

    client.read_range = Mock(
        return_value=Mock(
            spreadsheet_id="test-sheet-123",
            sheet_name="Sheet1",
            range_notation="A1:B2",
            cells=[],
        )
    )

    client.search_formulas = Mock(return_value=[])

    return client


@pytest.fixture
async def mock_memory_store(tmp_path: Path) -> AsyncGenerator[MemoryStore, None]:
    """Create an in-memory database for testing."""
    db_path = tmp_path / "test_memory.db"
    store = MemoryStore(str(db_path))
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def mock_anthropic_client() -> Mock:
    """Create a mocked Anthropic client."""
    client = Mock(spec=AnthropicClient)

    # Mock the messages.create method
    mock_response = Mock()
    mock_response.content = [Mock(text="Test response from Claude")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)

    client.client = Mock()
    client.client.messages = Mock()
    client.client.messages.create = Mock(return_value=mock_response)

    return client


@pytest.fixture
def mock_llm_response() -> dict:
    """Create a standard mock LLM response."""
    return {
        "content": [{"type": "text", "text": "This is a test response"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }


# Configure pytest-asyncio
def pytest_configure(config):
    """Configure pytest with asyncio settings."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
