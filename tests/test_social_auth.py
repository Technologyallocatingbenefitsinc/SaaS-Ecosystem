import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models import User
from app.database import get_db, Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, ANY

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(scope="module", autouse=True)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(autouse=True)
def mock_db_dependency():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_google_login_flow(monkeypatch):
    # app.dependency_overrides[get_db] = override_get_db # Handled by fixture
    
    # Mock httpx.AsyncClient.get for Google verification
    async def mock_get(*args, **kwargs):
        return MagicMock(status_code=200, json=lambda: {
            "email": "google_user@test.com",
            "sub": "google_12345",
            "name": "Google User",
            "picture": "http://pic.url"
        })
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        # 1. New Google User
        res = await ac.post("/auth/google", json={"id_token": "fake_jwt_token"})
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "google_user@test.com"
        assert data["credits"] == 1 # New user -> Free trial
        
        # 2. Existing Google User (Login)
        res2 = await ac.post("/auth/google", json={"id_token": "fake_jwt_token"})
        assert res2.status_code == 200
        assert res2.json()["user_id"] == data["user_id"]

@pytest.mark.asyncio
async def test_apple_login_flow():
    # app.dependency_overrides[get_db] = override_get_db # Handled by fixture
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        # 1. Apple Login (Mocked Token)
        res = await ac.post("/auth/apple", json={"id_token": "mock_apple_user_apple_001"})
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "user_apple_001@privaterelay.appleid.com"
        
        # 2. Invalid Token
        res_fail = await ac.post("/auth/apple", json={"id_token": "bad_token"})
        assert res_fail.status_code == 401
