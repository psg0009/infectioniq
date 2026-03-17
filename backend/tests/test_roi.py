"""Tests for ROI calculator"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_roi_calculate(client: AsyncClient):
    response = await client.post("/api/v1/roi/calculate", json={
        "annual_surgical_cases": 5000,
        "baseline_ssi_rate": 0.02,
        "avg_ssi_cost": 25000,
        "system_annual_cost": 50000,
        "expected_ssi_reduction": 0.30,
        "implementation_cost": 25000,
        "staff_training_hours": 40,
        "hourly_staff_rate": 50,
    })
    assert response.status_code == 200
    data = response.json()
    results = data["results"]
    assert results["baseline_ssi_cases"] == 100.0
    assert results["net_annual_savings"] > 0
    assert results["roi_percent"] > 0
