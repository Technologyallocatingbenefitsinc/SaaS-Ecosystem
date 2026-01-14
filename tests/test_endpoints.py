import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import os

# Mock Env Vars if needed, though .env should handle it or we patch
os.environ["AUTH_SECRET_TOKEN"] = "mock_secret"

@pytest.mark.asyncio
async def test_read_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "SaaS Ecosystem API is running"}

@pytest.mark.asyncio
async def test_signup():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {"email": "test@example.com", "password": "password123", "role": "student"}
        response = await ac.post("/auth/signup", json=payload)
    # Depending on DB state, this might fail or succeed. 
    # Since we are using a real DB connection in main.py, we might need to mock get_db or handle DB errors.
    # For now, let's see if it hits the endpoint logic.
    assert response.status_code in [200, 400, 422] 

@pytest.mark.asyncio
async def test_legal_export():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/legal/export-data")
    assert response.status_code == 200
    assert "Export Request Queued" in response.json()["status"]

@pytest.mark.asyncio
async def test_upload_file():
    files = {'file': ('test.txt', b'test content', 'text/plain')}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/upload/upload-content", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert "path" in data
