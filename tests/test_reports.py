"""Tests for reports endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_and_get_report(async_client, auth_headers):
    # Create report with base64 image and markdown
    content = "# Daily Report\n\n![Image](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==)\n\nAll systems nominal."
    response = await async_client.post(
        "/api/reports/2026-09-16",
        headers=auth_headers,
        json={"content": content, "content_type": "markdown"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-09-16"
    assert "All systems nominal" in data["content"]
    assert "data:image/png;base64" in data["content"]

    # Get report
    get_res = await async_client.get("/api/reports/2026-09-16", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["content"] == content


@pytest.mark.asyncio
async def test_append_report_default(async_client, auth_headers):
    # Upload first part
    part1 = "Part 1: Morning briefing."
    res1 = await async_client.post(
        "/api/reports/2026-09-17",
        headers=auth_headers,
        json={"content": part1, "content_type": "markdown"},
    )
    assert res1.status_code == 200

    # Upload second part without overwrite (default should append)
    part2 = "Part 2: Evening retrospective."
    res2 = await async_client.post(
        "/api/reports/2026-09-17",
        headers=auth_headers,
        json={"content": part2, "content_type": "markdown"},
    )
    assert res2.status_code == 200
    content = res2.json()["content"]
    assert part1 in content
    assert part2 in content
    assert "---" in content


@pytest.mark.asyncio
async def test_overwrite_report(async_client, auth_headers):
    # Upload initial
    await async_client.post(
        "/api/reports/2026-09-18",
        headers=auth_headers,
        json={"content": "Initial report", "content_type": "markdown"},
    )

    # Overwrite
    overwrite_content = "Completely new report"
    res = await async_client.post(
        "/api/reports/2026-09-18?overwrite=true",
        headers=auth_headers,
        json={"content": overwrite_content, "content_type": "markdown"},
    )
    assert res.status_code == 200
    assert res.json()["content"] == overwrite_content


@pytest.mark.asyncio
async def test_edit_report_put(async_client, auth_headers):
    # Put directly to edit text
    await async_client.post(
        "/api/reports/2026-09-19",
        headers=auth_headers,
        json={"content": "Typo in this line", "content_type": "mixed"},
    )

    # Viewer edits text
    put_res = await async_client.put(
        "/api/reports/2026-09-19",
        headers=auth_headers,
        json={"content": "Fixed typo in this line"},
    )
    assert put_res.status_code == 200
    assert put_res.json()["content"] == "Fixed typo in this line"


@pytest.mark.asyncio
async def test_list_reports_summary(async_client, auth_headers):
    await async_client.post(
        "/api/reports/2026-09-20",
        headers=auth_headers,
        json={"content": "Report for 20th", "content_type": "mixed"},
    )
    await async_client.post(
        "/api/reports/2026-09-21",
        headers=auth_headers,
        json={"content": "Report for 21st", "content_type": "mixed"},
    )

    res = await async_client.get("/api/reports", headers=auth_headers)
    assert res.status_code == 200
    dates = [r["date"] for r in res.json()]
    assert "2026-09-20" in dates
    assert "2026-09-21" in dates


@pytest.mark.asyncio
async def test_delete_report(async_client, auth_headers):
    await async_client.post(
        "/api/reports/2026-09-22",
        headers=auth_headers,
        json={"content": "To be deleted", "content_type": "mixed"},
    )

    del_res = await async_client.delete("/api/reports/2026-09-22", headers=auth_headers)
    assert del_res.status_code == 200

    # Getting deleted report returns 404
    get_res = await async_client.get("/api/reports/2026-09-22", headers=auth_headers)
    assert get_res.status_code == 404
