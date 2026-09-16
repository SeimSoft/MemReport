"""Tests for share endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_and_access_share_single_and_multi(async_client, auth_headers):
    # Create two reports
    await async_client.post(
        "/api/reports/2026-09-10",
        headers=auth_headers,
        json={"content": "Report 10th", "content_type": "mixed"},
    )
    await async_client.post(
        "/api/reports/2026-09-11",
        headers=auth_headers,
        json={"content": "Report 11th with **bold** text", "content_type": "markdown"},
    )

    # Create share link for both dates
    create_res = await async_client.post(
        "/api/shares",
        headers=auth_headers,
        json={
            "dates": ["2026-09-10", "2026-09-11"],
            "title": "Sprint Review Reports",
            "expires_in_days": 7,
        },
    )
    assert create_res.status_code == 200
    share_data = create_res.json()
    token = share_data["token"]
    assert len(share_data["dates"]) == 2
    assert "Sprint Review Reports" == share_data["title"]
    assert f"/share/{token}" in share_data["share_url"]

    # Access without ANY authentication headers (anonymous user)
    pub_res = await async_client.get(f"/api/public/shares/{token}")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()
    assert pub_data["title"] == "Sprint Review Reports"
    assert "2026-09-10" in pub_data["reports"]
    assert "2026-09-11" in pub_data["reports"]
    assert pub_data["reports"]["2026-09-10"]["content"] == "Report 10th"
    assert "Report 11th" in pub_data["reports"]["2026-09-11"]["content"]

    # List user's shares
    list_res = await async_client.get("/api/shares", headers=auth_headers)
    assert list_res.status_code == 200
    assert any(s["token"] == token for s in list_res.json())

    # Revoke share
    share_id = share_data["id"]
    del_res = await async_client.delete(f"/api/shares/{share_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # Public access now returns 404
    expired_res = await async_client.get(f"/api/public/shares/{token}")
    assert expired_res.status_code == 404
