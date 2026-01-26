import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_ai_polish_endpoint(monkeypatch):
    # Mock Gemini response
    mock_response = MagicMock()
    mock_response.text = "Rewritten text content."
    
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    
    # Mock the client instance in the router
    monkeypatch.setattr("app.routers.editor.client", mock_client)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        response = await ac.post("/editor/rewrite", json={
            "text": "Original text.",
            "tone": "Professional"
        })
    
    assert response.status_code == 200
    assert response.json()["rewritten_text"] == "Rewritten text content."
