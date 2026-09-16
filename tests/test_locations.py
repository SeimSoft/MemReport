"""Tests for report location (GPS) endpoints."""

import pytest


@pytest.mark.asyncio
async def test_set_and_get_location(async_client, auth_headers):
    # Create report first
    await async_client.post(
        "/api/reports/2026-09-16",
        headers=auth_headers,
        json={"content": "Report in Berlin", "content_type": "mixed"},
    )

    # Set GPS location
    loc_res = await async_client.put(
        "/api/reports/2026-09-16/location",
        headers=auth_headers,
        json={"latitude": 52.5200, "longitude": 13.4050, "name": "Berlin HQ"},
    )
    assert loc_res.status_code == 200
    data = loc_res.json()
    assert data["latitude"] == 52.5200
    assert data["longitude"] == 13.4050
    assert data["location_name"] == "Berlin HQ"

    # Verify via /api/locations endpoint
    list_loc_res = await async_client.get("/api/locations", headers=auth_headers)
    assert list_loc_res.status_code == 200
    items = list_loc_res.json()
    assert len(items) >= 1
    found = next((i for i in items if i["date"] == "2026-09-16"), None)
    assert found is not None
    assert found["latitude"] == 52.5200
    assert found["location_name"] == "Berlin HQ"


@pytest.mark.asyncio
async def test_delete_location(async_client, auth_headers):
    await async_client.post(
        "/api/reports/2026-09-17",
        headers=auth_headers,
        json={"content": "Munich report", "content_type": "mixed"},
    )
    await async_client.put(
        "/api/reports/2026-09-17/location",
        headers=auth_headers,
        json={"latitude": 48.1351, "longitude": 11.5820, "name": "Munich Lab"},
    )

    del_loc_res = await async_client.delete(
        "/api/reports/2026-09-17/location",
        headers=auth_headers,
    )
    assert del_loc_res.status_code == 200

    # Verify location is now null in report
    rep = await async_client.get("/api/reports/2026-09-17", headers=auth_headers)
    assert rep.json()["latitude"] is None
    assert rep.json()["longitude"] is None
