"""Test configuration and fixtures"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


# Test database engine (in-memory SQLite)
test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after"""
    from app.models import models
    from app.models.user import User
    from app.models.audit_log import AuditLog
    from app.models.consent import PatientConsent
    from app.core.tenant import Organization  # noqa: F401 — ensures table is created

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default organization for tenant isolation
    async with TestSessionLocal() as session:
        from app.core.tenant import DEFAULT_ORG_ID
        existing = await session.get(Organization, DEFAULT_ORG_ID)
        if not existing:
            session.add(Organization(
                id=DEFAULT_ORG_ID, name="Default Organization",
                slug="default", is_active=True, settings="{}",
            ))
            await session.commit()

    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Get a test database session"""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """Get an async test client"""
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    from app.core.tenant import DEFAULT_ORG_ID
    headers = {"X-Tenant-ID": DEFAULT_ORG_ID}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac
    app.dependency_overrides.clear()
