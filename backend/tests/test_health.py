"""Tests for health check endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")  # degraded is OK when Redis isn't available
    assert "components" in data
    assert "database" in data["components"]
    assert "scheduler" in data["components"]
    assert "cameras" in data["components"]
