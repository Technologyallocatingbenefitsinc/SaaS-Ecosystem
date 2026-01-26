import pytest
from app.main import app
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_generate_viral_clips():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        
        # Mock Transcript with Timestamps
        mock_transcript = [
            {'text': "Hello world", 'start': 0.0, 'duration': 2.0},
            {'text': "This is a viral moment", 'start': 2.0, 'duration': 5.0},
            {'text': "End of video", 'start': 7.0, 'duration': 2.0}
        ]
        
        # Mock Gemini Response
        mock_gemini = MagicMock()
        mock_gemini.text = '''
        [
            {
                "start_time": 2.0,
                "end_time": 7.0,
                "viral_score": 90,
                "reason": "High energy intro",
                "suggested_caption": "Viral!"
            }
        ]
        '''
        
        # Mock Client
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gemini

        with patch("app.services.gemini_engine.get_transcript", return_value=mock_transcript):
             with patch("app.services.gemini_engine.client", mock_client):
                res = await ac.post("/editor/generate-clips", json={"video_url": "https://youtube.com/watch?v=123"})
                assert res.status_code == 200
                data = res.json()
                assert "clips" in data
                assert len(data["clips"]) == 1
                assert data["clips"][0]["viral_score"] == 90
                assert data["clips"][0]["start_time"] == 2.0
