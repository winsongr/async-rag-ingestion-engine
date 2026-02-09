"""
Pytest fixtures for AI Data Platform tests.
Provides shared test infrastructure without testing libraries.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock
from src.domains.base import Base


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing queue operations."""
    redis = AsyncMock()
    redis.rpush = AsyncMock()
    redis.blpop = AsyncMock()
    redis.llen = AsyncMock(return_value=0)
    return redis


@pytest_asyncio.fixture
async def db_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create database session for tests."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
