"""Tests for camera endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_cameras_unauthorized(client: AsyncClient):
    """Camera list requires auth"""
    response = await client.get("/api/v1/cameras/")
    assert response.status_code == 401 or response.status_code == 403


@pytest.mark.asyncio
async def test_list_cameras_authenticated(client: AsyncClient):
    """Authenticated user can list cameras"""
    # Register and get token
    reg = await client.post("/api/v1/auth/register", json={
        "email": "cam@example.com",
        "password": "CamPass123!",
        "full_name": "Cam User",
    })
    token = reg.json()["access_token"]

    response = await client.get(
        "/api/v1/cameras/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "cameras" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_camera_not_found(client: AsyncClient):
    """Getting a non-existent camera returns 404"""
    response = await client.get("/api/v1/cameras/nonexistent-cam")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_camera_heartbeat_requires_auth(client: AsyncClient):
    """Camera heartbeat without auth should fail"""
    response = await client.post("/api/v1/cameras/heartbeat", json={
        "camera_id": "cam-or1",
        "or_number": "OR-1",
        "status": "ONLINE",
        "fps": 30.0,
        "resolution": "1920x1080",
    })
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_camera_heartbeat_with_auth(client: AsyncClient):
    """Camera heartbeat with auth registers the camera"""
    reg = await client.post("/api/v1/auth/register", json={
        "email": "hb@example.com",
        "password": "HeartBeat123!",
        "full_name": "HB User",
    })
    token = reg.json()["access_token"]

    response = await client.post(
        "/api/v1/cameras/heartbeat",
        json={
            "camera_id": "cam-or1",
            "or_number": "OR-1",
            "status": "ONLINE",
            "fps": 30.0,
            "resolution": "1920x1080",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_camera_health_summary(client: AsyncClient):
    """Camera health summary returns aggregate stats"""
    response = await client.get("/api/v1/cameras/health/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "online" in data
    assert "health_percent" in data
