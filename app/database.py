import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/dbname")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Fix for Neon/Replit: Remove sslmode=require if present to avoid asyncpg errors
if "postgres" in DATABASE_URL:
    try:
        parsed = urlparse(DATABASE_URL)
        query_params = parse_qs(parsed.query)
        if 'sslmode' in query_params:
            query_params.pop('sslmode', None)
            new_query = urlencode(query_params, doseq=True)
            DATABASE_URL = urlunparse(parsed._replace(query=new_query))
    except Exception:
        pass

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Keeps 20 connections ready at all times
    max_overflow=10,       # Can open 10 extra during traffic spikes
    pool_pre_ping=True,    # Prevents 'Connection Lost' errors on Replit
    echo=False
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
