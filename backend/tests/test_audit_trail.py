"""
Tests for the blockchain-like audit trail.
"""
import pytest

from database import database
from db.models import AuditTrail
from core.audit_logger import log_event, verify_chain


@pytest.fixture(autouse=True)
def clean_audit_trail():
    with database:
        AuditTrail.delete().execute()
    yield


class TestAuditLogger:
    def test_log_event_creates_entry(self):
        with database:
            entry = log_event("test_action", "alice", resource_type="task", resource_id="123")
        assert entry.action == "test_action"
        assert entry.actor == "alice"
        assert entry.current_hash != entry.previous_hash

    def test_chain_links_entries(self):
        with database:
            first = log_event("action_1", "alice")
            second = log_event("action_2", "bob")
        assert second.previous_hash == first.current_hash

    def test_verify_chain_valid(self):
        with database:
            log_event("action_1", "alice")
            log_event("action_2", "bob")
            result = verify_chain()
        assert result["valid"] is True
        assert result["checked_count"] == 2

    def test_verify_chain_detects_tampering(self):
        with database:
            log_event("action_1", "alice")
            log_event("action_2", "bob")
            # Tamper with the latest entry
            latest = AuditTrail.select().order_by(AuditTrail.timestamp.desc()).first()
            latest.action = "tampered"
            latest.save()
            result = verify_chain()
        assert result["valid"] is False
        assert result["first_invalid_id"] is not None


class TestAuditAPI:
    @pytest.fixture
    def sync_client(self):
        from fastapi.testclient import TestClient
        from main import app
        with TestClient(app) as c:
            yield c

    def _auth_headers(self, sync_client):
        resp = sync_client.post("/api/v1/auth/login", json={"username": "admin", "password": "testpass123"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_list_audit_entries(self, sync_client):
        headers = self._auth_headers(sync_client)
        with database:
            AuditTrail.create(
                action="login",
                actor="alice",
                resource_type="user",
                resource_id="u1",
                previous_hash="0" * 64,
                current_hash="a" * 64,
            )

        resp = sync_client.get("/api/v1/audit", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["action"] == "login"

    def test_verify_endpoint(self, sync_client):
        headers = self._auth_headers(sync_client)
        with database:
            log_event("api_event", "tester")

        resp = sync_client.get("/api/v1/audit/verify", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["checked_count"] >= 1

    def test_create_audit_entry(self, sync_client):
        # Get admin token
        resp = sync_client.post("/api/v1/auth/login", json={"username": "admin", "password": "testpass123"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        body = {"action": "manual", "actor": "admin", "resource_type": "task", "resource_id": "t1"}
        resp = sync_client.post("/api/v1/audit", json=body, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["action"] == "manual"
        assert data["current_hash"] is not None
