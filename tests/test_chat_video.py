import pytest
import sys
from unittest.mock import MagicMock

# Mock gTTS before importing app modules
sys.modules["gtts"] = MagicMock()
sys.modules["gtts.gTTS"] = MagicMock()

from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import patch

@pytest.fixture
def mock_gemini_chat():
    with patch("app.services.gemini_engine.client") as mock_client:
        mock_response = MagicMock()
        mock_response.text = "This is a mock answer based on the video."
        mock_client.models.generate_content.return_value = mock_response
        yield mock_client

@pytest.mark.asyncio
async def test_chat_with_video(mock_gemini_chat):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        payload = {
            "text": "This is a transcript about Python functions.",
            "history": [{"role": "model", "text": "Hello"}],
            "question": "What is a function?"
        }
        response = await ac.post("/editor/chat-video", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "This is a mock answer based on the video."
