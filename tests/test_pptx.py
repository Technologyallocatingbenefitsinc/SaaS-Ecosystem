import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app

# Mock response from Gemini
MOCK_GEMINI_JSON = """
[
    {
        "title": "Slide 1",
        "content": "Bullet A\\nBullet B"
    },
    {
        "title": "Slide 2",
        "content": "Conclusion"
    }
]
"""

@pytest.mark.asyncio
async def test_export_pptx_endpoint():
    # Mock Gemini Service
    with patch("app.routers.editor.convert_text_to_slides_json", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = MOCK_GEMINI_JSON
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
            response = await ac.post("/editor/export-pptx", json={"text": "Some study notes content"})
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        # Check standard Zip signature (PK)
        assert response.content.startswith(b"PK")
