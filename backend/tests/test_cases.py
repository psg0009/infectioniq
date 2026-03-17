"""Tests for cases and compliance endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_case_not_found(client: AsyncClient):
    response = await client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_staff(client: AsyncClient):
    response = await client.get("/api/v1/staff/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_dispensers(client: AsyncClient):
    response = await client.get("/api/v1/dispensers/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient):
    response = await client.get("/api/v1/alerts/")
    assert response.status_code == 200
