"""Tests for authentication endpoints."""

import pytest


@pytest.mark.asyncio
async def test_register_user(async_client):
    response = await async_client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "securepassword"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_username_fails(async_client):
    response = await async_client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "anotherpassword"},
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(async_client):
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["username"] == "testuser"
    # Verify cookie is set
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_fails(async_client):
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(async_client, auth_headers):
    response = await async_client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
