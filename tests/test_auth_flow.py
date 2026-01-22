import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models import User
from app.database import get_db, Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.routers.auth import hash_password
from datetime import datetime, timedelta, timezone

# Helper to setup DB
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

import pytest_asyncio

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
async def test_signup_fingerprint_abuse():
    # app.dependency_overrides[get_db] = override_get_db # Handled by fixture
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        
        # 1. First User (Fresh Fingerprint)
        res1 = await ac.post("/auth/signup", json={
            "email": "user1@test.com", 
            "password": "p1", 
            "device_fingerprint": "fp_001"
        })
        assert res1.status_code == 201
        assert res1.json()["credits"] == 1 # Gets free trial

        # 2. Second User (SAME Fingerprint) -> Abuse
        res2 = await ac.post("/auth/signup", json={
            "email": "user2@test.com", 
            "password": "p2", 
            "device_fingerprint": "fp_001"
        })
        assert res2.status_code == 201
        assert res2.json()["credits"] == 0 # No free trial!

@pytest.mark.asyncio
async def test_reset_password_flow():
    # app.dependency_overrides[get_db] = override_get_db # Handled by fixture
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        # Prep: Create user
        await ac.post("/auth/signup", json={"email": "reset_me@test.com", "password": "old_password"})
        
        # 1. Forgot Password
        with pytest.MonkeyPatch.context() as m:
            # Mock the N8n call to avoid network err
            # We don't verify the N8n call here (integration test), just the response
            res_forgot = await ac.post("/auth/forgot-password", json={"email": "reset_me@test.com"})
            assert res_forgot.status_code == 200
            
        # 2. Manually verify token exist in DB (cheating for test)
        async with TestingSessionLocal() as session:
            result = await session.execute(
                # Import select locally to avoid module-level issues if not imported
                pytest.importorskip("sqlalchemy.future").select(User).where(User.email == "reset_me@test.com")
            )
            user = result.scalars().first()
            assert user.reset_token is not None
            token = user.reset_token
            
        # 3. Reset Password
        res_reset = await ac.post("/auth/reset-password", json={
            "token": token,
            "new_password": "new_secure_password"
        })
        assert res_reset.status_code == 200
        
        # 4. Login with OLD password (should fail)
        res_fail = await ac.post("/auth/login", json={
            "email": "reset_me@test.com", "password": "old_password"
        })
        assert res_fail.status_code == 401
        
        # 5. Login with NEW password (should success)
        res_ok = await ac.post("/auth/login", json={
            "email": "reset_me@test.com", "password": "new_secure_password"
        })
        assert res_ok.status_code == 200
