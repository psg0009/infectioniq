"""Tests for FHIR R4 endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_capability_statement(client: AsyncClient):
    response = await client.get("/api/v1/fhir/metadata")
    assert response.status_code == 200
    data = response.json()
    assert data["resourceType"] == "CapabilityStatement"
    assert data["fhirVersion"] == "4.0.1"


@pytest.mark.asyncio
async def test_procedure_not_found(client: AsyncClient):
    response = await client.get("/api/v1/fhir/Procedure/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_practitioner_not_found(client: AsyncClient):
    response = await client.get("/api/v1/fhir/Practitioner/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_observation_requires_case(client: AsyncClient):
    response = await client.get("/api/v1/fhir/Observation")
    assert response.status_code == 400
