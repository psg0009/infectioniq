"""Tests for compliance endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_compliance_entry_missing_case(client: AsyncClient):
    """Entry event with non-existent case should fail"""
    response = await client.post("/api/v1/compliance/entry", json={
        "case_id": "00000000-0000-0000-0000-000000000000",
        "person_track_id": 1,
        "zone": "CRITICAL",
        "sanitized_before_entry": True,
    })
    # Should get an error (404 or 500) because case doesn't exist
    assert response.status_code >= 400


@pytest.mark.asyncio
async def test_compliance_exit_accepts_request(client: AsyncClient):
    """Exit endpoint accepts a well-formed request"""
    response = await client.post(
        "/api/v1/compliance/exit",
        params={"case_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_compliance_sanitize_accepts_request(client: AsyncClient):
    """Sanitize endpoint accepts a well-formed request"""
    response = await client.post(
        "/api/v1/compliance/sanitize",
        params={"case_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 200
