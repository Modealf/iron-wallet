import os

# Force the production singleton in db.session to point at the test database.
os.environ.setdefault(
    "DATABASE_URL",
    "cockroachdb+asyncpg://root@localhost:26257/investment_wallet_test",
)

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import db.session as session_mod
from db.models.model_base import Base
import db.models.models  # noqa: F401  -- registers all models


SYNC_TEST_URL = "cockroachdb://root@localhost:26257/investment_wallet_test"
ASYNC_TEST_URL = "cockroachdb+asyncpg://root@localhost:26257/investment_wallet_test"


def _reset_schema() -> None:
    sync_engine = create_engine(SYNC_TEST_URL, future=True)
    with sync_engine.begin() as conn:
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
    sync_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Simple async session per test (Phase 2-style). Schema reset before yielding."""
    _reset_schema()
    engine = create_async_engine(ASYNC_TEST_URL, future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory():
    """Yields the sessionmaker itself (NullPool) so handlers under test can open
    multiple sessions across the same test."""
    _reset_schema()
    engine = create_async_engine(ASYNC_TEST_URL, future=True, poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm
    await engine.dispose()


def _patched_get_engine(db_name: str):
    """Test variant of db.session.get_engine: NullPool so each request opens a
    fresh asyncpg connection on whatever event loop it runs on (TestClient
    spins up a fresh anyio loop per request)."""
    if session_mod._engine is None:
        session_mod._engine = create_async_engine(ASYNC_TEST_URL, poolclass=NullPool)
        session_mod._sessionmaker = async_sessionmaker(
            session_mod._engine, expire_on_commit=False, class_=AsyncSession
        )
    return session_mod._engine


@pytest.fixture
def db_for_client(monkeypatch):
    """For TestClient-driven controller tests: drop+recreate schema, patch
    db.session so live request handlers use a NullPool async engine pointed at
    the test DB."""
    _reset_schema()

    session_mod._engine = None
    session_mod._sessionmaker = None
    monkeypatch.setattr(session_mod, "get_engine", _patched_get_engine)

    yield None

    session_mod._engine = None
    session_mod._sessionmaker = None
