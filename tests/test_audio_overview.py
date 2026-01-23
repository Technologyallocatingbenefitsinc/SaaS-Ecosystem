import pytest
import sys
from unittest.mock import MagicMock

# Mock gTTS before importing app modules that depend on it
sys.modules["gtts"] = MagicMock()
sys.modules["gtts.gTTS"] = MagicMock()

from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import patch

@pytest.fixture
def mock_gemini_audio():
    with patch("app.routers.editor.generate_audio_script") as mock:
        mock.return_value = '''[
            {"speaker": "Alex", "text": "Hello world"},
            {"speaker": "Sam", "text": "Hi Alex"}
        ]'''
        yield mock

@pytest.fixture
def mock_audio_synth():
    with patch("app.routers.editor.synthesize_podcast_audio") as mock:
        mock.return_value = "user_uploads/test_podcast.mp3"
        yield mock

@pytest.mark.asyncio
async def test_generate_audio_script(mock_gemini_audio):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        response = await ac.post("/editor/generate-audio-script", json={"text": "Some transcript"})
    
    assert response.status_code == 200
    data = response.json()
    assert "script" in data
    assert len(data["script"]) == 2
    assert data["script"][0]["speaker"] == "Alex"

@pytest.mark.asyncio
async def test_synthesize_audio(mock_audio_synth):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        script = [
            {"speaker": "Alex", "text": "Hello world"},
            {"speaker": "Sam", "text": "Hi Alex"}
        ]
        response = await ac.post("/editor/synthesize-audio", json={"script": script})
    
    assert response.status_code == 200
    data = response.json()
    assert "audio_url" in data
    assert data["audio_url"].startswith("/uploads/podcast_")
    assert data["audio_url"].endswith(".mp3")
