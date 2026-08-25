"""
Tests for agent auto-update and on-demand module pull endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from database import database
from db.models import Agent, Module, Task


@pytest.fixture(autouse=True)
def clean_agent_update_data():
    database.execute_sql("PRAGMA foreign_keys = OFF")
    try:
        with database:
            database.execute_sql("DELETE FROM tasks")
            database.execute_sql("DELETE FROM agents")
            database.execute_sql("DELETE FROM modules")
    finally:
        database.execute_sql("PRAGMA foreign_keys = ON")
    yield


class TestAgentUpdateAPI:
    @pytest.fixture
    def client(self):
        from main import app
        with TestClient(app) as c:
            yield c

    def _auth_headers(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "testpass123"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def _create_agent(self):
        with database:
            return Agent.create(hostname="update-host", os="windows", username="user", status="online")

    def test_request_agent_update(self, client):
        headers = self._auth_headers(client)
        a = self._create_agent()
        resp = client.post(
            f"/api/v1/agents/{a.id}/update",
            json={"version": "1.2.3", "url": "https://cdn.example.com/agent.zip", "force": True},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"] is True
        assert "task_id" in data

        # Verify task was created with the right module/action
        with database:
            task = Task.get(Task.id == data["task_id"])
        assert task.module == "agent_update"
        assert task.action == "update"
        assert task.params_dict["version"] == "1.2.3"

    def test_request_agent_update_not_found(self, client):
        headers = self._auth_headers(client)
        resp = client.post(
            "/api/v1/agents/00000000-0000-0000-0000-000000000000/update",
            json={"version": "1.0.0"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_pull_module(self, client):
        headers = self._auth_headers(client)
        a = self._create_agent()
        with database:
            Module.create(
                name="keylogger",
                version="2.0.0",
                code="def run(**kwargs): return {}",
                signature="sig",
                enabled=True,
            )
        resp = client.post(
            f"/api/v1/agents/{a.id}/pull-module/keylogger",
            json={"force": True},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"] is True
        assert "task_id" in data

        with database:
            task = Task.get(Task.id == data["task_id"])
        assert task.module == "module_pull"
        assert task.action == "pull"
        assert task.params_dict["module_name"] == "keylogger"
        assert task.params_dict["version"] == "2.0.0"

    def test_pull_module_not_found(self, client):
        headers = self._auth_headers(client)
        a = self._create_agent()
        resp = client.post(
            f"/api/v1/agents/{a.id}/pull-module/nonexistent",
            json={},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_update_status_endpoint(self, client):
        headers = self._auth_headers(client)
        a = self._create_agent()
        with database:
            Task.create(
                agent=a,
                module="agent_update",
                action="update",
                status="queued",
                params="{}",
            )
        resp = client.get(f"/api/v1/agents/{a.id}/update-status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == str(a.id)
        assert len(data["tasks"]) >= 1
        assert all(t["module"] in ("agent_update", "module_pull") for t in data["tasks"])

    def test_update_unauthorized(self, client):
        a = self._create_agent()
        resp = client.post(f"/api/v1/agents/{a.id}/update", json={"version": "1.0.0"})
        assert resp.status_code == 401
