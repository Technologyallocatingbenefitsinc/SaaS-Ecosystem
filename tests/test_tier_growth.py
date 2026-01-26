import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings

@pytest.mark.asyncio
async def test_generate_blog_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
        # Mocking the gemini response might be better but let's check routing first
        # Since GEMINI_API_KEY is 'mock', the real call will fail, so we should mock the service
        from unittest.mock import patch
        with patch("app.routers.editor.generate_blog_from_text") as mock_gen:
            mock_gen.return_value = "This is a mock blog post content."
            response = await ac.post("/editor/generate-blog", json={
                "text": "Transcript content string",
                "language": "English"
            })
            if response.status_code != 200:
                print(f"DEBUG_BLOG: {response.status_code} - {response.text}")
            assert response.status_code == 200
            assert "blog" in response.json()
            assert response.json()["blog"] == "This is a mock blog post content."

@pytest.mark.asyncio
async def test_generate_carousel_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
        from unittest.mock import patch
        with patch("app.routers.editor.generate_carousel_from_text") as mock_gen:
            mock_gen.return_value = "Slide 1: Hook\nSlide 2: Content"
            response = await ac.post("/editor/generate-carousel", json={
                "text": "Transcript content string",
                "language": "English"
            })
            if response.status_code != 200:
                print(f"DEBUG_CAROUSEL: {response.status_code} - {response.text}")
            assert response.status_code == 200
            assert "carousel" in response.json()
            assert response.json()["carousel"] == "Slide 1: Hook\nSlide 2: Content"

@pytest.mark.asyncio
async def test_landing_page_tiers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
        response = await ac.get("/")
        if response.status_code != 200:
            print(f"DEBUG_LANDING: {response.status_code} - {response.text}")
        assert response.status_code == 200
        content = response.text
        assert "Student" in content
        assert "Educator" in content
        assert "Podcaster" in content
        assert "Course Pro" in content
        assert "$9.99" in content
        assert "$19" in content
        assert "$29" in content
        assert "$49" in content
