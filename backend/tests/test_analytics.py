"""Tests for analytics endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_metrics(client: AsyncClient):
    response = await client.get("/api/v1/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "active_cases" in data
    assert "overall_compliance_rate" in data


@pytest.mark.asyncio
async def test_trends(client: AsyncClient):
    response = await client.get("/api/v1/analytics/trends?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "trends" in data


@pytest.mark.asyncio
async def test_violations(client: AsyncClient):
    response = await client.get("/api/v1/analytics/violations?days=30")
    assert response.status_code == 200
    data = response.json()
    assert "violations" in data
