"""
Integration tests for Project Lucy REST API.
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
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_success(async_client):
    resp = await async_client.post("/api/v1/auth/login", json={"username": "admin", "password": "testpass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(async_client):
    resp = await async_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(async_client, auth_headers):
    resp = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_agents_list(async_client, auth_headers):
    resp = await async_client.get("/api/v1/agents", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_tasks_list(async_client, auth_headers):
    resp = await async_client.get("/api/v1/tasks", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_modules_list(async_client, auth_headers):
    resp = await async_client.get("/api/v1/modules", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_groups_list(async_client, auth_headers):
    resp = await async_client.get("/api/v1/groups", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_timelines_list(async_client, auth_headers):
    resp = await async_client.get("/api/v1/timelines", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_logs_list(async_client, auth_headers):
    resp = await async_client.get("/api/v1/logs", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_monitor_stats(async_client, auth_headers):
    resp = await async_client.get("/api/v1/monitor/stats", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_denied(async_client):
    resp = await async_client.get("/api/v1/agents")
    assert resp.status_code == 401
