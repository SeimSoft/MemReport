"""Pytest fixtures for MemReport."""

import os
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

# Set test database inside workspace ./tmp/ or temporary test db
TMP_DIR = Path(__file__).resolve().parent.parent / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB_PATH = TMP_DIR / "test_memreport.db"

os.environ["MEMREPORT_DB_PATH"] = str(TEST_DB_PATH)

from memreport.config import settings
settings.db_path = TEST_DB_PATH

from memreport.main import app
from memreport.database import init_db
from memreport.auth import hash_password
from memreport.database import create_user


@pytest.fixture(autouse=True)
async def prepare_database():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    await init_db()
    # Create test user (admin)
    pw_hash = hash_password("testpass123")
    await create_user("testuser", pw_hash, is_admin=True)
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def auth_headers(async_client):
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
