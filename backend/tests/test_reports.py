"""Tests for reports and export endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_compliance_csv(client: AsyncClient):
    response = await client.get("/api/v1/reports/compliance/csv?days=7")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_cases_csv(client: AsyncClient):
    response = await client.get("/api/v1/reports/cases/csv?days=7")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_alerts_csv(client: AsyncClient):
    response = await client.get("/api/v1/reports/alerts/csv?days=7")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_report_summary(client: AsyncClient):
    response = await client.get("/api/v1/reports/summary?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "cases" in data
    assert "compliance" in data
    assert "alerts" in data


@pytest.mark.asyncio
async def test_pricing(client: AsyncClient):
    response = await client.get("/api/v1/pricing/")
    assert response.status_code == 200
    data = response.json()
    assert "tiers" in data
    assert len(data["tiers"]) == 3
