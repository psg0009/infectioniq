"""
Opt-in PostgreSQL test fixtures.

These fixtures only activate when TEST_DATABASE_URL is set to a PostgreSQL URL,
e.g.:  TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/testdb pytest -k postgres
"""

import os
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base

POSTGRES_URL = os.getenv("TEST_DATABASE_URL", "")

requires_postgres = pytest.mark.skipif(
    not POSTGRES_URL or "postgresql" not in POSTGRES_URL,
    reason="TEST_DATABASE_URL not set to a PostgreSQL URL",
)


@pytest_asyncio.fixture
async def pg_engine():
    """Create a PostgreSQL engine for testing. Skips if not configured."""
    if not POSTGRES_URL or "postgresql" not in POSTGRES_URL:
        pytest.skip("TEST_DATABASE_URL not set to a PostgreSQL URL")

    engine = create_async_engine(POSTGRES_URL, echo=False)

    # Import all models so metadata is complete
    from app.models import models  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.audit_log import AuditLog  # noqa: F401
    from app.models.consent import PatientConsent  # noqa: F401
    from app.services.clinical_validation import ValidationSession, ValidationObservation  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine):
    """Get a PostgreSQL test session."""
    SessionLocal = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
        await session.rollback()
