"""Agent API tests."""
from config import settings


def _login(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_agent_register_missing_public_key(client):
    """Agent registration must 422 when the required public_key is missing."""
    resp = client.post(
        "/api/v1/agents/register",
        json={
            "hostname": "test-host",
            "os": "linux",
            "username": "testuser",
        },
    )
    assert resp.status_code == 422
    detail = resp.text.lower()
    assert "public_key" in detail


def test_agents_list_unauthorized(client):
    """Protected agent list requires authentication."""
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 401
    assert "Not authenticated" in resp.json().get("detail", "")


def test_agents_list_authorized(client):
    """Authenticated users can list agents."""
    token = _login(client)
    resp = client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
