import pytest
from app.main import app
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_generate_quiz():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        
        # Mock Gemini response for Quiz
        mock_response = MagicMock()
        mock_response.text = '''
        [
            {
                "question": "What is Python?",
                "options": ["Snake", "Language", "Food", "Car"],
                "answer": "Language"
            }
        ]
        '''
        
        with patch("google.generativeai.GenerativeModel.generate_content", return_value=mock_response):
            res = await ac.post("/editor/generate-quiz", json={"text": "Python is a programming language."})
            assert res.status_code == 200
            data = res.json()
            assert "questions" in data
            assert len(data["questions"]) == 1
            assert data["questions"][0]["answer"] == "Language"

@pytest.mark.asyncio
async def test_generate_flashcards():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        
        # Mock Gemini response for Flashcards
        mock_response = MagicMock()
        mock_response.text = '''
        [
            {
                "front": "Python",
                "back": "A programming language"
            }
        ]
        '''
        
        with patch("google.generativeai.GenerativeModel.generate_content", return_value=mock_response):
            res = await ac.post("/editor/generate-flashcards", json={"text": "Python is a programming language."})
            assert res.status_code == 200
            data = res.json()
            assert "flashcards" in data
            assert len(data["flashcards"]) == 1
            assert data["flashcards"][0]["front"] == "Python"
