"""
Multi-Tenant Support
Organization-based data isolation
"""

import logging
from typing import Optional
from fastapi import Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import get_db, Base
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
import uuid

logger = logging.getLogger(__name__)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    settings = Column(Text, default="{}")  # JSON string for org-specific settings
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def get_tenant_id(request: Request) -> Optional[str]:
    """Extract tenant ID from request header or subdomain"""
    # Check header first
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        return tenant_id

    # Check subdomain
    host = request.headers.get("host", "")
    parts = host.split(".")
    if len(parts) >= 3:
        return parts[0]

    return None


async def get_current_tenant(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Optional[Organization]:
    """Get current tenant organization"""
    tenant_id = get_tenant_id(request)
    if not tenant_id:
        return None

    result = await db.execute(
        select(Organization).where(
            (Organization.id == tenant_id) | (Organization.slug == tenant_id)
        )
    )
    return result.scalar_one_or_none()


DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# Paths that skip tenant enforcement
_TENANT_SKIP_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json", "/metrics"}


class TenantMiddleware(BaseHTTPMiddleware):
    """Extracts tenant ID from request and stores it in request.state."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip tenant check for health/docs/metrics
        if path in _TENANT_SKIP_PATHS:
            request.state.tenant_id = None
            return await call_next(request)

        tenant_id = get_tenant_id(request)

        if tenant_id is None:
            # In dev/test, default to the default org
            from app.config import settings
            if settings.ENVIRONMENT in ("development", "test"):
                tenant_id = DEFAULT_ORG_ID
            elif path.startswith("/api/") and not path.startswith("/api/v1/auth"):
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=400,
                    content={"detail": "X-Tenant-ID header required"},
                )

        request.state.tenant_id = tenant_id
        return await call_next(request)


def get_tenant_query_filter(model, org_id: Optional[str], bypass: bool = False):
    """Return a SQLAlchemy filter clause for tenant isolation.
    Returns ``True`` (no-op) when bypass is set, org_id is None, or the model
    doesn't have an organization_id column."""
    if bypass or org_id is None or not hasattr(model, "organization_id"):
        return True
    return model.organization_id == org_id
