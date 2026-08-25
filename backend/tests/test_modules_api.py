"""
Module store API tests for Project Lucy.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture
async def async_client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(async_client):
    resp = await async_client.post("/api/v1/auth/login", json={"username": "admin", "password": "testpass123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_module_upload(async_client, auth_headers):
    payload = {
        "name": "test_module",
        "version": "1.0.0",
        "description": "A test module",
        "code": "def run(**kwargs):\n    return {'status': 'ok', 'data': {}}",
        "dependencies": [],
        "os_compat": ["windows", "linux", "darwin"],
    }
    resp = await async_client.post("/api/v1/modules", json=payload, headers=auth_headers)
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "test_module"
    return data["id"]


@pytest.mark.asyncio
async def test_module_list(async_client, auth_headers):
    resp = await async_client.get("/api/v1/modules", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_module_delete(async_client, auth_headers):
    payload = {
        "name": "del_module",
        "version": "0.1.0",
        "description": "To delete",
        "code": "def run(**kwargs): return {}",
        "dependencies": [],
        "os_compat": ["linux"],
    }
    create = await async_client.post("/api/v1/modules", json=payload, headers=auth_headers)
    mid = create.json()["id"]
    resp = await async_client.delete(f"/api/v1/modules/{mid}", headers=auth_headers)
    assert resp.status_code in (200, 204)
