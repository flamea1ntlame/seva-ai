import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_supabase(monkeypatch):
    import os
    from unittest.mock import MagicMock

    # Mock settings so we hit the supabase branches
    from app.config import settings
    monkeypatch.setattr(settings, "SUPABASE_URL", "http://mock-supabase.local")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-key")
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_BUCKET", "seva-documents")

    mock_client = MagicMock()

    def mock_download(path):
        # We need to return some bytes representing a file
        return b"mock file content"

    mock_client.storage.from_().download.side_effect = mock_download
    mock_client.storage.from_().upload.return_value = None
    mock_client.storage.from_().remove.return_value = None

    def mock_create_client(url, key):
        return mock_client

    monkeypatch.setattr("supabase.create_client", mock_create_client)
    return mock_client
