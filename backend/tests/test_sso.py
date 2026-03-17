"""Tests for SSO endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sso_login_disabled(client: AsyncClient):
    """SSO login returns 400 when SSO is disabled"""
    response = await client.get("/api/v1/sso/login")
    assert response.status_code == 400
    assert "not enabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sso_metadata_disabled(client: AsyncClient):
    """SSO metadata returns 400 when SSO is disabled"""
    response = await client.get("/api/v1/sso/metadata")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_sso_logout_disabled(client: AsyncClient):
    """SSO logout returns 400 when SSO is disabled"""
    response = await client.get("/api/v1/sso/logout")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_sso_acs_disabled(client: AsyncClient):
    """SSO ACS returns 400 when SSO is disabled"""
    response = await client.post(
        "/api/v1/sso/acs",
        data={"SAMLResponse": "dGVzdA=="},
    )
    assert response.status_code == 400
