"""Tests for consent endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_record_consent(client: AsyncClient):
    """Create a patient consent record"""
    response = await client.post("/api/v1/consent/", json={
        "patient_id": "PAT-001",
        "consent_type": "DATA_COLLECTION",
        "consented_by": "Dr. Smith",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["patient_id"] == "PAT-001"
    assert data["consent_type"] == "DATA_COLLECTION"
    assert data["status"] == "GRANTED"


@pytest.mark.asyncio
async def test_get_patient_consents(client: AsyncClient):
    """List consents for a patient"""
    # Create a consent first
    await client.post("/api/v1/consent/", json={
        "patient_id": "PAT-002",
        "consent_type": "AI_MONITORING",
        "consented_by": "Dr. Jones",
    })
    response = await client.get("/api/v1/consent/patient/PAT-002")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["patient_id"] == "PAT-002"


@pytest.mark.asyncio
async def test_check_consent_status(client: AsyncClient):
    """Check consent status for a patient"""
    response = await client.get("/api/v1/consent/patient/PAT-NONE/status")
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "PAT-NONE"
    assert data["all_granted"] is False
    assert len(data["missing"]) > 0


@pytest.mark.asyncio
async def test_revoke_consent(client: AsyncClient):
    """Revoke a consent record"""
    # Create consent
    create = await client.post("/api/v1/consent/", json={
        "patient_id": "PAT-003",
        "consent_type": "DATA_COLLECTION",
        "consented_by": "Dr. Smith",
    })
    consent_id = create.json()["id"]

    # Revoke it
    response = await client.post(f"/api/v1/consent/{consent_id}/revoke", json={
        "reason": "Patient requested withdrawal",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_revoke_nonexistent_consent(client: AsyncClient):
    """Revoking a non-existent consent returns 404"""
    response = await client.post(
        "/api/v1/consent/00000000-0000-0000-0000-000000000000/revoke",
        json={"reason": "test"},
    )
    assert response.status_code == 404
