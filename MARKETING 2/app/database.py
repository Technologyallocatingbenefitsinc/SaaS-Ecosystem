import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/dbname")

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
