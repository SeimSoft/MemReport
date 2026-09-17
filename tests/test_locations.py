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


@pytest.mark.asyncio
async def test_route_extraction_in_locations(async_client, auth_headers):
    report_content = """# Wanderung
```leaflet
{
  "title": "Alpenrunde",
  "distance_km": 12.5,
  "elevation_gain_m": 450,
  "coordinates": [
    [47.5, 11.2],
    [47.51, 11.22],
    [47.52, 11.24]
  ]
}
```
"""
    await async_client.put(
        "/api/reports/2026-09-25",
        headers=auth_headers,
        json={"content": report_content, "content_type": "mixed"},
    )

    list_res = await async_client.get("/api/locations", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()
    item = next((i for i in items if i["date"] == "2026-09-25"), None)
    assert item is not None
    assert item["latitude"] == 47.5
    assert item["longitude"] == 11.2
    assert item["location_name"] == "Alpenrunde"
    assert item["routes"] is not None
    assert len(item["routes"]) == 1
    assert item["routes"][0]["title"] == "Alpenrunde"
    assert len(item["routes"][0]["coordinates"]) == 3

