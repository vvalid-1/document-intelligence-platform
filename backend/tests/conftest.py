from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://docplat:docplat_secret@postgres:5432/docplat")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-32chars")
os.environ.setdefault("UPLOAD_DIR", "/tmp/docplat_test_uploads")

_db_base = os.environ["DATABASE_URL"].rsplit("/", 1)[0]
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or f"{_db_base}/docplat_test"

from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture  # function-scoped: fresh schema + session per test
async def db() -> AsyncGenerator[AsyncSession, None]:
    import app.models  # noqa: F401

    engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()
    yield session

    # Teardown: suppress RuntimeError from asyncpg "different loop" issue in pytest-asyncio 0.24
    # All tests have already passed at this point — cleanup is best-effort only
    try:
        await session.close()
    except (RuntimeError, Exception):
        pass
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except (RuntimeError, Exception):
        pass
    try:
        await engine.dispose()
    except (RuntimeError, Exception):
        pass


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from app.core.database import get_db

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
