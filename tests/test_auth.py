"""Tests for authentication endpoints."""

import pytest


@pytest.mark.asyncio
async def test_register_user_by_admin(async_client, auth_headers):
    response = await async_client.post(
        "/api/auth/register",
        headers=auth_headers,
        json={"username": "newuser", "password": "securepassword"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_user_unauthorized_fails(async_client):
    response = await async_client.post(
        "/api/auth/register",
        json={"username": "unauthorized_user", "password": "securepassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_register_user(async_client, auth_headers):
    # Admin creates a regular user
    reg_res = await async_client.post(
        "/api/auth/register",
        headers=auth_headers,
        json={"username": "regular_guy", "password": "password123", "is_admin": False},
    )
    assert reg_res.status_code == 201

    # Login as regular user
    login_res = await async_client.post(
        "/api/auth/login",
        json={"username": "regular_guy", "password": "password123"},
    )
    reg_token = login_res.json()["access_token"]
    reg_headers = {"Authorization": f"Bearer {reg_token}"}

    # Attempt to create another user
    res = await async_client.post(
        "/api/auth/register",
        headers=reg_headers,
        json={"username": "another_user", "password": "password123"},
    )
    assert res.status_code == 403
    assert "Nur Administratoren" in res.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username_fails(async_client, auth_headers):
    response = await async_client.post(
        "/api/auth/register",
        headers=auth_headers,
        json={"username": "testuser", "password": "anotherpassword"},
    )
    assert response.status_code == 400
    assert "bereits vergeben" in response.json()["detail"]


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


@pytest.mark.asyncio
async def test_update_profile_username_and_password(async_client, auth_headers):
    # Change username and password
    res = await async_client.put(
        "/api/auth/me",
        headers=auth_headers,
        json={
            "current_password": "testpass123",
            "new_username": "testuser_renamed",
            "new_password": "newsecretpassword",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "testuser_renamed"

    # Login with new credentials
    login_new = await async_client.post(
        "/api/auth/login",
        json={"username": "testuser_renamed", "password": "newsecretpassword"},
    )
    assert login_new.status_code == 200


@pytest.mark.asyncio
async def test_update_profile_wrong_current_password_fails(async_client, auth_headers):
    res = await async_client.put(
        "/api/auth/me",
        headers=auth_headers,
        json={
            "current_password": "wrong_old_password",
            "new_username": "fail_name",
        },
    )
    assert res.status_code == 400
    assert "Passwort ist nicht korrekt" in res.json()["detail"]


@pytest.mark.asyncio
async def test_logout_endpoint(async_client):
    res = await async_client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.json()["message"] == "Logged out successfully"
