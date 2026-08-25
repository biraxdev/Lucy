"""
Tests for the live dashboard heatmap endpoint.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from database import database
from db.models import Agent, Credential, FileEvent, Log, Task
from core.heatmap_engine import HeatmapEngine


@pytest.fixture(autouse=True)
def clean_heatmap_data():
    with database:
        Task.delete().execute()
        Log.delete().execute()
        Credential.delete().execute()
        FileEvent.delete().execute()
        Agent.delete().execute()
    yield


class TestHeatmapEngine:
    @pytest.fixture
    def engine(self):
        return HeatmapEngine()

    def test_time_heatmap_has_cells(self, engine):
        with database:
            Agent.create(hostname="host-a", os="windows", username="alice", status="online")
        result = engine.heatmap("time")
        assert result["mode"] == "time"
        assert result["x_label"] == "Hour of day (UTC)"
        assert len(result["cells"]) == 7 * 24

    def test_agent_heatmap_counts_tasks(self, engine):
        with database:
            a = Agent.create(hostname="host-a", os="windows", username="alice", status="online")
            Task.create(agent=a, module="shell", action="whoami", status="completed", params="{}")
        result = engine.heatmap("agent", hours_window=24)
        assert result["mode"] == "agent"
        assert "host-a" in result["y_axis"]
        assert sum(c["v"] for c in result["cells"]) >= 1

    def test_heatmap_aggregates_multiple_sources(self, engine):
        with database:
            a = Agent.create(hostname="host-b", os="linux", username="root", status="online")
            Task.create(agent=a, module="shell", action="run", status="completed", params="{}")
            Log.create(level="INFO", module="agent", message="heartbeat", agent=a)
            Credential.create(
                agent=a,
                username="admin",
                source="chrome",
                confidence="high",
                password_encrypted="enc",
                url="https://example.com",
            )
            FileEvent.create(agent=a, path="/tmp/secret.txt", action="upload")
        result = engine.heatmap("agent", hours_window=24)
        total = sum(c["v"] for c in result["cells"])
        assert total >= 4

    def test_time_heatmap_recent_activity(self, engine):
        now = datetime.now(timezone.utc)
        with database:
            a = Agent.create(hostname="host-c", os="windows", username="user", status="online")
            Task.create(agent=a, module="info", action="run", status="completed", params="{}", created_at=now)
        result = engine.heatmap("time")
        hour_index = now.weekday() * 24 + now.hour
        assert any(c["v"] > 0 for c in result["cells"])


class TestDashboardHeatmapAPI:
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

    def test_heatmap_time_endpoint(self, client):
        headers = self._auth_headers(client)
        with database:
            Agent.create(hostname="api-host", os="windows", username="alice", status="online")
        resp = client.get("/api/v1/dashboard/heatmap?by=time", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "time"
        assert len(data["cells"]) == 7 * 24

    def test_heatmap_agent_endpoint(self, client):
        headers = self._auth_headers(client)
        with database:
            a = Agent.create(hostname="api-agent", os="linux", username="root", status="online")
            Task.create(agent=a, module="shell", action="whoami", status="completed", params="{}")
        resp = client.get("/api/v1/dashboard/heatmap?by=agent&hours=24", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "agent"
        assert "api-agent" in data["y_axis"]
        assert sum(c["v"] for c in data["cells"]) >= 1

    def test_heatmap_unauthorized(self, client):
        resp = client.get("/api/v1/dashboard/heatmap")
        assert resp.status_code == 401
