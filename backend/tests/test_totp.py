"""
Tests for TOTP MFA endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from database import database
from db.models import User
from core.auth import hash_password
from core.totp import generate_code


@pytest.fixture(autouse=True)
def seed_totp_user():
    with database:
        user = User.get_or_none(User.username == "mfauser")
        if user:
            User.update(
                password_hash=hash_password("testpass123"),
                role="admin",
                totp_secret=None,
                totp_enabled=False,
            ).where(User.id == user.id).execute()
        else:
            user = User.create(
                username="mfauser",
                password_hash=hash_password("testpass123"),
                role="admin",
            )
    yield user
    try:
        with database:
            User.update(totp_secret=None, totp_enabled=False).where(User.username == "mfauser").execute()
    except PermissionError:
        pass


class TestTotpMfa:
    @pytest.fixture
    def client(self):
        from main import app
        with TestClient(app) as c:
            yield c

    def _login(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "mfauser", "password": "testpass123"})
        assert resp.status_code == 200
        return resp.json()["access_token"]

    def test_totp_generate_and_verify(self, client):
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert "provisioning_uri" in data
        assert "otpauth" in data["provisioning_uri"]

        secret = data["secret"]
        code = generate_code(secret)
        resp = client.post("/api/v1/auth/mfa/verify", json={"code": code}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_login_requires_mfa_after_enabled(self, client, seed_totp_user):
        # enable MFA
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}
        setup = client.post("/api/v1/auth/mfa/setup", headers=headers)
        secret = setup.json()["secret"]
        code = generate_code(secret)
        client.post("/api/v1/auth/mfa/verify", json={"code": code}, headers=headers)

        # normal login now returns MFA challenge
        resp = client.post("/api/v1/auth/login", json={"username": "mfauser", "password": "testpass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("mfa_required") is True
        assert "access_token" not in data

        # complete MFA login
        code = generate_code(secret)
        resp = client.post("/api/v1/auth/mfa/login", json={"username": "mfauser", "password": "testpass123", "code": code})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_mfa_login_invalid_code(self, client, seed_totp_user):
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}
        setup = client.post("/api/v1/auth/mfa/setup", headers=headers)
        secret = setup.json()["secret"]
        code = generate_code(secret)
        client.post("/api/v1/auth/mfa/verify", json={"code": code}, headers=headers)

        resp = client.post(
            "/api/v1/auth/mfa/login",
            json={"username": "mfauser", "password": "testpass123", "code": "000000"},
        )
        assert resp.status_code == 401

    def test_verify_invalid_code(self, client):
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/api/v1/auth/mfa/setup", headers=headers)
        resp = client.post("/api/v1/auth/mfa/verify", json={"code": "000000"}, headers=headers)
        assert resp.status_code == 400

    def test_setup_already_enabled(self, client, seed_totp_user):
        token = self._login(client)
        headers = {"Authorization": f"Bearer {token}"}
        setup = client.post("/api/v1/auth/mfa/setup", headers=headers)
        secret = setup.json()["secret"]
        code = generate_code(secret)
        client.post("/api/v1/auth/mfa/verify", json={"code": code}, headers=headers)
        resp = client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert resp.status_code == 400
