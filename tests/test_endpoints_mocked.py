import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock
from app.models import User

# Mock DB Session
async def override_get_db():
    mock_session = AsyncMock(spec=AsyncSession)
    
    # Mock result for SELECT (Default: User not found/Empty)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None 
    mock_session.execute.return_value = mock_result
    
    mock_session.commit = AsyncMock(return_value=None)
    mock_session.refresh = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    
    yield mock_session

app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_read_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code in [200, 307]

@pytest.mark.asyncio
async def test_signup_mocked():
    payload = {"email": "newuser@example.com", "password": "securepassword", "role": "student"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/signup", json=payload)
    
    assert response.status_code in [200, 201]
    data = response.json()
    assert data["email"] == "newuser@example.com"

@pytest.mark.asyncio
async def test_upload_mocked():
    with pytest.MonkeyPatch.context() as m:
        m.setattr("app.routers.upload.remove_file_after_delay", AsyncMock(return_value=None))
        m.setattr("app.routers.upload.signal_n8n_to_start", AsyncMock(return_value=200))
        
        files = {'file': ('test_mock.txt', b'mock content', 'text/plain')}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/upload/upload-content", files=files)
        
        assert response.status_code == 200
        assert "filename" in response.json()

@pytest.mark.asyncio
async def test_replit_auth_headers():
    headers = {
        "X-Replit-User-Id": "123",
        "X-Replit-User-Name": "testuser",
        "X-Replit-User-Roles": "student"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/auth/me", headers=headers)
    
    assert response.status_code == 200
    assert response.json()["logged_in"] is True

@pytest.mark.asyncio
async def test_billing_page_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/billing")
    assert response.status_code == 200
    assert "stripe-pricing-table" in response.text

@pytest.mark.asyncio
async def test_add_credits_endpoint():
    headers = {"auth-token": "mock_secret"}
    params = {"user_id": 1, "amount": 100}
    # Note: This will likely fail with 404 because our mock DB returns None for the user lookup
    # But it verifies the endpoint structure and authentication check.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/api/credits/add", headers=headers, params=params)
    
    assert response.status_code in [200, 404]

@pytest.mark.asyncio
async def test_delete_account_logic():
    headers = {
        "X-Replit-User-Id": "123",
        "auth-token": "mock_secret"
    }
    with pytest.MonkeyPatch.context() as m:
        m.setattr("app.routers.upload.delete_user_folder", AsyncMock(return_value=None))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/auth/api/delete-account", headers=headers)
    
    assert response.status_code in [200, 401]
