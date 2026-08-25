"""Backend authentication API tests."""
import pytest

from config import settings


def _login(client, username=None, password=None):
    """Return the access token for the default admin user."""
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": username or settings.ADMIN_USERNAME,
            "password": password or settings.ADMIN_PASSWORD,
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_login_valid(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data.get("token_type") == "bearer"


def test_login_invalid(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json().get("detail", "")


def test_refresh_token(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    ).json()
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


def test_rate_limit_auth_login(client):
    """The login endpoint is limited to 10/minute — repeated failures should 429."""
    codes = []
    for _ in range(12):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": "wrong"},
        )
        codes.append(resp.status_code)
    assert 401 in codes, "failed credentials should return 401"
    assert 429 in codes, "rate limit should eventually return 429"


def test_unauthorized_agents(client):
    """Protected agent listing must reject requests without a token."""
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 401
    assert "Not authenticated" in resp.json().get("detail", "")


def test_me_unauthorized(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
