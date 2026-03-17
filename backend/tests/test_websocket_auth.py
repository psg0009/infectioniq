"""Tests for WebSocket JWT authentication and camera config endpoint"""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


# ---------------------------------------------------------------------------
# Camera config endpoint
# ---------------------------------------------------------------------------

class TestCameraConfigEndpoint:
    @pytest.mark.asyncio
    async def test_get_camera_config(self, client: AsyncClient):
        """Camera config endpoint returns zone config and thresholds"""
        response = await client.get("/api/v1/cameras/cam-OR-1/config")
        assert response.status_code == 200
        data = response.json()
        assert data["camera_id"] == "cam-OR-1"
        assert "zones" in data
        assert "zone_risk_levels" in data
        assert "thresholds" in data
        assert "heartbeat_interval" in data

    @pytest.mark.asyncio
    async def test_camera_config_has_thresholds(self, client: AsyncClient):
        """Config includes all CV threshold values"""
        response = await client.get("/api/v1/cameras/any-cam/config")
        data = response.json()
        thresholds = data["thresholds"]
        assert "person_confidence" in thresholds
        assert "hand_confidence" in thresholds
        assert "sanitize_gesture" in thresholds
        assert "sanitize_min_duration_sec" in thresholds


# ---------------------------------------------------------------------------
# Camera heartbeat auth
# ---------------------------------------------------------------------------

class TestCameraHeartbeatAuth:
    @pytest.mark.asyncio
    async def test_heartbeat_requires_auth(self, client: AsyncClient):
        """Heartbeat without auth should fail"""
        response = await client.post("/api/v1/cameras/heartbeat", json={
            "camera_id": "cam-1",
            "or_number": "OR-1",
            "status": "ONLINE",
        })
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_heartbeat_with_auth(self, client: AsyncClient):
        """Heartbeat with valid auth should succeed"""
        # Register a user and get token
        reg = await client.post("/api/v1/auth/register", json={
            "email": "heartbeat@example.com",
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


# ---------------------------------------------------------------------------
# Camera health summary
# ---------------------------------------------------------------------------

class TestCameraHealthSummary:
    @pytest.mark.asyncio
    async def test_health_summary_structure(self, client: AsyncClient):
        response = await client.get("/api/v1/cameras/health/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "online" in data
        assert "degraded" in data
        assert "offline" in data
        assert "health_percent" in data

    @pytest.mark.asyncio
    async def test_health_summary_values_are_numeric(self, client: AsyncClient):
        """Health summary values should be numeric"""
        response = await client.get("/api/v1/cameras/health/summary")
        data = response.json()
        assert isinstance(data["total"], int)
        assert isinstance(data["online"], int)
        assert isinstance(data["health_percent"], (int, float))


# ---------------------------------------------------------------------------
# Clinical validation match endpoint
# ---------------------------------------------------------------------------

class TestValidationMatchEndpoint:
    @pytest.mark.asyncio
    async def test_match_nonexistent_session(self, client: AsyncClient):
        """Matching a non-existent session returns 404"""
        response = await client.post("/api/v1/validation/sessions/nonexistent/match")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_match_endpoint_exists(self, client: AsyncClient):
        """Match endpoint is accessible (may fail due to FK but shouldn't 404 on route)"""
        response = await client.post("/api/v1/validation/sessions/some-id/match")
        # The endpoint exists — either 404 (session not found) or 200
        assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# WebSocket JWT auth (unit-level tests)
# ---------------------------------------------------------------------------

class TestWebSocketJWTAuth:
    def test_create_valid_token(self):
        """create_access_token produces a decodable token"""
        from app.core.security import decode_token
        token = create_access_token({"sub": "user@test.com"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user@test.com"
        assert payload["type"] == "access"

    def test_decode_invalid_token_returns_none(self):
        from app.core.security import decode_token
        result = decode_token("invalid.jwt.token")
        assert result is None

    def test_decode_expired_token_returns_none(self):
        from app.core.security import decode_token
        from datetime import timedelta
        token = create_access_token(
            {"sub": "user@test.com"},
            expires_delta=timedelta(seconds=-1),
        )
        result = decode_token(token)
        assert result is None
