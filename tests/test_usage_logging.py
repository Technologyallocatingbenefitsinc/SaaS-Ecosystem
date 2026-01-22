import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.services.usage_logger import log_token_usage
from app.services.gemini_engine import process_video_content
from app.config import settings

@pytest.mark.asyncio
async def test_cost_calculation():
    # Test rates: $0.075/1M in, $0.30/1M out
    # 1M tokens in = $0.075
    # 1M tokens out = $0.30
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        settings.N8N_TOKEN_LOGGER_URL = "http://mock-n8n.com"
        await log_token_usage(user_id=123, plan_type="student", prompt_tokens=1000000, response_tokens=1000000)
        
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        
        assert payload["cost_usd"] == 0.075 + 0.30
        assert payload["user_id"] == 123

@pytest.mark.asyncio
async def test_gemini_engine_logging_integration():
    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_response = AsyncMock()
        mock_response.text = "Mocked AI Response"
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        
        # GenerativeModel.generate_content is not async usually but the wrapper might be
        mock_model.return_value.generate_content.return_value = mock_response
        
        with patch("app.services.gemini_engine.log_token_usage", new_callable=AsyncMock) as mock_logger:
            with patch("app.services.gemini_engine.get_transcript", return_value="Mocked Transcript"):
                result = await process_video_content("http://youtube.com/v=123", "student", 456)
                
                assert result["content"] == "<p>Mocked AI Response</p>"
                mock_logger.assert_called_once_with(
                    user_id=456,
                    plan_type="student",
                    prompt_tokens=100,
                    response_tokens=50
                )
