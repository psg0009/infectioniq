"""Tests for authentication endpoints"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "TestPass123!",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "TestPass123!",
        "full_name": "Test User",
    })
    response = await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "TestPass123!",
        "full_name": "Test User 2",
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "TestPass123!",
        "full_name": "Login User",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "TestPass123!",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com",
        "password": "TestPass123!",
        "full_name": "Wrong Pass User",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "wrong@example.com",
        "password": "WrongPassword!",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "me@example.com",
        "password": "TestPass123!",
        "full_name": "Me User",
    })
    token = reg.json()["access_token"]
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403 or response.status_code == 401


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Password must meet complexity requirements"""
    response = await client.post("/api/v1/auth/register", json={
        "email": "weak@example.com",
        "password": "password",  # no uppercase, no digit, no special
        "full_name": "Weak Pass",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """Test token refresh flow"""
    reg = await client.post("/api/v1/auth/register", json={
        "email": "refresh@example.com",
        "password": "RefreshPass1!",
        "full_name": "Refresh User",
    })
    refresh_token = reg.json()["refresh_token"]
    response = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    """Test password change"""
    reg = await client.post("/api/v1/auth/register", json={
        "email": "change@example.com",
        "password": "OldPass123!",
        "full_name": "Change User",
    })
    token = reg.json()["access_token"]
    response = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "OldPass123!", "new_password": "NewPass456!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
