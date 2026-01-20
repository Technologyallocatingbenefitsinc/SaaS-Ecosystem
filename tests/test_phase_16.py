import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import AsyncMock, patch
from app.database import get_db

@pytest.mark.asyncio
async def test_legal_routes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        for route in ["/tos", "/trust-center", "/privacy"]:
            response = await ac.get(route)
            assert response.status_code == 200
            assert "MODYFIRE" in response.text

@pytest.mark.asyncio
async def test_process_video_with_slide_count():
    # Mocking the engine call to avoid real API
    with patch("app.main.process_video_content", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = {"status": "success", "content": "mocked slides"}
        
        headers = {"x-n8n-auth": "mock_secret"}
        params = {
            "video_url": "https://youtube.com/watch?v=123",
            "user_id": 1,
            "user_tier": "podcaster",
            "slide_count": "11-18"
        }
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
            response = await ac.post("/process-video", headers=headers, params=params)
        
        assert response.status_code == 200
        mock_process.assert_called_once_with(
            "https://youtube.com/watch?v=123", 
            "podcaster", 
            1, 
            "11-18"
        )

@pytest.mark.asyncio
async def test_upload_video_form_with_slide_count():
    with patch("app.main.process_video_content", new_callable=AsyncMock) as mock_process:
        # We mock what the service returns
        mock_process.return_value = {
            "tier": "student",
            "model": "gemini-2.5-flash", 
            "content": "Mocked summary content"
        }
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
            data = {
                "video_url": "https://youtube.com/watch?v=123",
                "slide_count": "1-5"
            }
            response = await ac.post("/upload-video", data=data)
            
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["content"] == "Mocked summary content"
        # We also verify the mock was called with correct args
        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[0][0] == "https://youtube.com/watch?v=123"
        assert call_args[0][3] == "1-5"
