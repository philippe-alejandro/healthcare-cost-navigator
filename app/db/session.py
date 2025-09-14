import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def get_database_url() -> str:
    # Fallback to localhost for dev if not running in Docker
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/healthcare",
    )


ASYNC_ENGINE = create_async_engine(get_database_url(), future=True, echo=False)
ASYNC_SESSION_MAKER = async_sessionmaker(ASYNC_ENGINE, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with ASYNC_SESSION_MAKER() as session:
        yield session


