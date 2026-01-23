import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_process_video_with_language():
    # Mock the gemini engine function
    with patch("app.main.process_video_content", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = {"content": "Translated Summary"}
        
        headers = {"x-n8n-auth": "test"}
        params = {
            "video_url": "https://youtube.com/watch?v=12345",
            "language": "Spanish"
        }
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
            response = await ac.post("/process-video", params=params, headers=headers)
        
        assert response.status_code == 200
        # Verify language was passed to the service
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args.kwargs
        # The function signature is (video_url, user_tier, user_id, slide_count, language)
        # So we check if language='Spanish' is in kwargs
        assert call_kwargs.get('language') == "Spanish"

@pytest.mark.asyncio
async def test_editor_endpoints_with_language():
    # Mock authentication
    with patch("app.routers.auth.get_replit_user") as mock_user:
        mock_user.return_value.id = 1
        mock_user.return_value.tier = "student"
        
        # Test Quiz Generation
        with patch("app.routers.editor.generate_quiz_from_text", new_callable=AsyncMock) as mock_quiz:
            mock_quiz.return_value = '[{"question": "Que?", "options": ["Si", "No"], "answer": "Si"}]'
            
            payload = {"text": "Hello world", "language": "French"}
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
                response = await ac.post("/editor/generate-quiz", json=payload)
            
            assert response.status_code == 200
            mock_quiz.assert_called_once()
            assert mock_quiz.call_args.kwargs.get('language') == "French"

        # Test Flashcard Generation
        with patch("app.routers.editor.generate_flashcards_from_text", new_callable=AsyncMock) as mock_cards:
            mock_cards.return_value = '[{"front": "Hola", "back": "Hello"}]'
            
            payload = {"text": "Hello world", "language": "German"}
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
                response = await ac.post("/editor/generate-flashcards", json=payload)
            
            assert response.status_code == 200
            mock_cards.assert_called_once()
            assert mock_cards.call_args.kwargs.get('language') == "German"

