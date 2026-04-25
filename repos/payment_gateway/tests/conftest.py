import os
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models.model_base import Base
import db.models.models  # noqa: F401


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    url = os.getenv(
        "TEST_DATABASE_URL",
        "cockroachdb+asyncpg://root@localhost:26257/payment_gateway_test",
    )
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        yield session
    await engine.dispose()
