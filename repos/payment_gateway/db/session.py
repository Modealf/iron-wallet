import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "cockroachdb+asyncpg://root@localhost:26257/{db}?sslmode=disable",
)

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine(db_name: str):
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL.format(db=db_name), pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_sessionmaker(db_name: str) -> async_sessionmaker[AsyncSession]:
    get_engine(db_name)
    assert _sessionmaker is not None
    return _sessionmaker


async def session_dependency(db_name: str):
    """FastAPI Depends() — yields an async session, commits on success, rolls back on error."""
    sm = get_sessionmaker(db_name)
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
