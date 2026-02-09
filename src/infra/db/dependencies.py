from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.db.postgres import SessionLocal


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to yield an AsyncSession per request.
    Ensures the session is closed after use.
    """
    async with SessionLocal() as session:
        yield session
