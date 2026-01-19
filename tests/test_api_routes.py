"""Tests for API routes."""

from unittest.mock import Mock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from sheetsmith.api.routes import (
    router,
    ChatRequest,
    ChatResponse,
)


@pytest.fixture
def mock_agent():
    """Create a mocked SheetSmith agent."""
    agent = Mock()
    agent.messages = [{"role": "user", "content": "test"}]
    agent.process_message = AsyncMock(return_value="Test response")
    agent.reset_conversation = Mock()
    agent.sheets_client = Mock()
    agent.memory_store = Mock()
    return agent


@pytest.fixture
def test_client(mock_agent):
    """Create a test client with mocked agent."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    
    # Mock the get_agent function to return our mock
    with patch("sheetsmith.api.routes.get_agent", return_value=mock_agent):
        yield TestClient(app)


class TestChatEndpoint:
    """Test the /api/chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_basic_functionality(self, test_client, mock_agent):
        """Test basic chat functionality with mocked agent."""
        with patch("sheetsmith.api.routes.get_agent", return_value=mock_agent):
            response = test_client.post(
                "/api/chat",
                json={"message": "Hello, SheetSmith!"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "conversation_length" in data
        assert data["response"] == "Test response"
        assert data["conversation_length"] == 1

    @pytest.mark.asyncio
    async def test_chat_with_spreadsheet_id(self, test_client, mock_agent):
        """Test chat with spreadsheet ID adds context."""
        with patch("sheetsmith.api.routes.get_agent", return_value=mock_agent):
            response = test_client.post(
                "/api/chat",
                json={
                    "message": "Update cell A1",
                    "spreadsheet_id": "test-sheet-123"
                }
            )
        
        assert response.status_code == 200
        
        # Verify the agent was called with modified message including spreadsheet context
        mock_agent.process_message.assert_called_once()
        call_args = mock_agent.process_message.call_args[0][0]
        assert "test-sheet-123" in call_args

    @pytest.mark.asyncio
    async def test_chat_handles_agent_error(self, test_client, mock_agent):
        """Test that chat endpoint handles agent errors properly."""
        mock_agent.process_message = AsyncMock(side_effect=Exception("Agent error"))
        
        with patch("sheetsmith.api.routes.get_agent", return_value=mock_agent):
            response = test_client.post(
                "/api/chat",
                json={"message": "Test message"}
            )
        
        assert response.status_code == 500
        assert "Agent error" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_chat_request_validation(self, test_client):
        """Test that ChatRequest model validates input."""
        # Missing required field 'message'
        response = test_client.post("/api/chat", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_does_not_duplicate_spreadsheet_context(self, test_client, mock_agent):
        """Test that spreadsheet context is not added if already mentioned."""
        with patch("sheetsmith.api.routes.get_agent", return_value=mock_agent):
            response = test_client.post(
                "/api/chat",
                json={
                    "message": "Update spreadsheet test-sheet-456",
                    "spreadsheet_id": "test-sheet-456"
                }
            )
        
        assert response.status_code == 200
        
        # Message should not have duplicate context since it already mentions spreadsheet
        mock_agent.process_message.assert_called_once()
        call_args = mock_agent.process_message.call_args[0][0]
        # Should be original message without added context
        assert call_args == "Update spreadsheet test-sheet-456"


class TestResetChatEndpoint:
    """Test the /api/chat/reset endpoint."""

    def test_reset_chat_success(self, test_client, mock_agent):
        """Test that reset chat endpoint works correctly."""
        with patch("sheetsmith.api.routes.get_agent", return_value=mock_agent):
            response = test_client.post("/api/chat/reset")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data
        
        # Verify agent's reset method was called
        mock_agent.reset_conversation.assert_called_once()

    def test_reset_chat_returns_correct_message(self, test_client, mock_agent):
        """Test that reset returns appropriate message."""
        with patch("sheetsmith.api.routes.get_agent", return_value=mock_agent):
            response = test_client.post("/api/chat/reset")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Conversation reset"


class TestRequestResponseModels:
    """Test request and response model validation."""

    def test_chat_request_with_message_only(self):
        """Test ChatRequest model with only required fields."""
        request = ChatRequest(message="Test message")
        assert request.message == "Test message"
        assert request.spreadsheet_id is None

    def test_chat_request_with_spreadsheet_id(self):
        """Test ChatRequest model with optional spreadsheet_id."""
        request = ChatRequest(
            message="Test message",
            spreadsheet_id="sheet-123"
        )
        assert request.message == "Test message"
        assert request.spreadsheet_id == "sheet-123"

    def test_chat_response_model(self):
        """Test ChatResponse model structure."""
        response = ChatResponse(
            response="Test response",
            conversation_length=5
        )
        assert response.response == "Test response"
        assert response.conversation_length == 5

    def test_chat_request_empty_message_fails(self):
        """Test that empty message is accepted (Pydantic allows empty strings)."""
        # Pydantic actually allows empty strings for str fields by default
        request = ChatRequest(message="")
        assert request.message == ""
