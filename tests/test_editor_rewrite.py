import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_ai_polish_endpoint(monkeypatch):
    # Mock Gemini response
    mock_response = MagicMock()
    mock_response.text = "Rewritten text content."
    
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    # Mock the GenerativeModel constructor to return our mock model
    monkeypatch.setattr("google.generativeai.GenerativeModel", MagicMock(return_value=mock_model))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        response = await ac.post("/editor/rewrite", json={
            "text": "Original text.",
            "tone": "Professional"
        })
    
    assert response.status_code == 200
    assert response.json()["rewritten_text"] == "Rewritten text content."
