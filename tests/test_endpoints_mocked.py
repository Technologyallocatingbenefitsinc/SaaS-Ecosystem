import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

# Mock DB Session
async def override_get_db():
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Mock result for SELECT (User not found)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None 
    mock_session.execute.return_value = mock_result
    
    # Mock commit/refresh to explicitly return None (though AsyncMock does this)
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None
    
    yield mock_session

app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_read_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_signup_mocked():
    payload = {"email": "newuser@example.com", "password": "securepassword", "role": "student"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # We need to rely on the fact that Auth Router mocks hashing or we just let it hash
        # Passlib should work fine in memory.
        response = await ac.post("/auth/signup", json=payload)
    
    assert response.status_code in [200, 201]
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "credits" in data

@pytest.mark.asyncio
async def test_upload_mocked(tmp_path):
    with pytest.MonkeyPatch.context() as m:
        # Mock the background cleanup to avoid 24h sleep
        m.setattr("app.routers.upload.remove_file_after_delay", AsyncMock(return_value=None))
        m.setattr("app.routers.upload.signal_n8n_to_start", AsyncMock(return_value=200))
        
        files = {'file': ('test_mock.txt', b'mock content', 'text/plain')}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/upload/upload-content", files=files)
        
        assert response.status_code == 200
        assert response.json()["filename"] == "test_mock.txt"
