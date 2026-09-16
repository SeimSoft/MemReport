"""Tests for web page rendering endpoints."""

import pytest


@pytest.mark.asyncio
async def test_login_page_renders(async_client):
    response = await async_client.get("/login")
    assert response.status_code == 200
    assert "MemReport" in response.text
    assert "Benutzername" in response.text


@pytest.mark.asyncio
async def test_viewer_page_redirects_when_unauthenticated(async_client):
    response = await async_client.get("/viewer", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_viewer_page_renders_when_authenticated(async_client, auth_headers):
    # Pass cookie or header
    login_res = await async_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    cookie_token = login_res.cookies.get("access_token")

    response = await async_client.get("/viewer", cookies={"access_token": cookie_token})
    assert response.status_code == 200
    assert "MemReport" in response.text
    assert "testuser" in response.text
    assert "Kartenansicht" in response.text


@pytest.mark.asyncio
async def test_share_page_public_renders(async_client, auth_headers):
    # Create report and share
    await async_client.post(
        "/api/reports/2026-09-16",
        headers=auth_headers,
        json={"content": "Public report test", "content_type": "mixed"},
    )
    share_res = await async_client.post(
        "/api/shares",
        headers=auth_headers,
        json={"dates": ["2026-09-16"], "title": "Test Shared Report"},
    )
    token = share_res.json()["token"]

    # Access public page with NO cookies/auth
    response = await async_client.get(f"/share/{token}")
    assert response.status_code == 200
    assert "Test Shared Report" in response.text
    assert token in response.text


@pytest.mark.asyncio
async def test_share_page_invalid_token_renders_404(async_client):
    response = await async_client.get("/share/non-existent-token-12345")
    assert response.status_code == 404
    assert "nicht verfügbar" in response.text or "abgelaufen" in response.text
