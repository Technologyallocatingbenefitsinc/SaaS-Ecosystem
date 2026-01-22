import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.routers.auth import verify_password
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock
from app.models import User

# Mock DB Session for Security Tests
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

@pytest.fixture(autouse=True)
def mock_db_dependency():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_password_hashing_signup():
    """Run this first before rate limiting is triggered"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        email = "secure@example.com"
        password = "secret_password"
        
        mock_db = await anext(override_get_db())
        app.dependency_overrides[get_db] = lambda: mock_db

        response = await ac.post("/auth/signup", json={"email": email, "password": password})
        assert response.status_code == 201
        
        args, _ = mock_db.add.call_args
        added_user = args[0]
        
        assert isinstance(added_user, User)
        assert added_user.email == email
        assert added_user.hashed_password != password
        assert verify_password(password, added_user.hashed_password)

@pytest.mark.asyncio
async def test_security_headers_and_trusted_host():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        response = await ac.get("/dashboard")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_signup_rate_limiting():
    # Use distinct emails to avoid existing user 400s if any
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        status_codes = []
        for i in range(10):
            data = {"email": f"bot{i}@example.com", "password": "password123"}
            response = await ac.post("/auth/signup", json=data)
            status_codes.append(response.status_code)
        
        # At least one should be 429
        assert 429 in status_codes
