"""
Tests for the unified full-text search API.
"""
import pytest
from fastapi.testclient import TestClient

from database import database
from db.models import Agent, Task, Log, Finding, AuditTrail
from core.search_engine import SearchEngine


@pytest.fixture(autouse=True)
def clean_search_data():
    with database:
        Task.delete().execute()
        Log.delete().execute()
        Finding.delete().execute()
        AuditTrail.delete().execute()
        Agent.delete().execute()
    yield


class TestSearchEngine:
    @pytest.fixture
    def engine(self):
        return SearchEngine()

    def test_search_finds_agent(self, engine):
        with database:
            Agent.create(hostname="workstation-01", os="windows", username="alice", status="online")
        result = engine.search("workstation")
        assert result["total"] >= 1
        assert any(r["type"] == "agent" and "workstation-01" in r["title"] for r in result["results"])

    def test_search_finds_task(self, engine):
        with database:
            a = Agent.create(hostname="host", os="linux", username="root", status="online")
            Task.create(agent=a, module="shell", action="whoami", status="completed", params="{}")
        result = engine.search("whoami")
        assert any(r["type"] == "task" for r in result["results"])

    def test_search_finds_log(self, engine):
        with database:
            Log.create(level="ERROR", module="auth", message="login failed for user admin")
        result = engine.search("login failed")
        assert any(r["type"] == "log" for r in result["results"])

    def test_search_with_type_filter(self, engine):
        with database:
            Agent.create(hostname="web-server", os="linux", username="root", status="online")
            Log.create(level="INFO", module="agent", message="web-server connected")
        result = engine.search("web", types=["agent"])
        assert all(r["type"] == "agent" for r in result["results"])

    def test_search_multiple_tokens(self, engine):
        with database:
            Agent.create(hostname="db-server", os="windows", username="admin", status="online")
        result = engine.search("db windows")
        assert result["total"] >= 1

    def test_empty_query_returns_no_results(self, engine):
        result = engine.search("")
        assert result["total"] == 0


class TestSearchAPI:
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

    def test_search_endpoint(self, client):
        headers = self._auth_headers(client)
        with database:
            Agent.create(hostname="search-host", os="windows", username="alice", status="online")
        resp = client.get("/api/v1/search?q=search-host", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(r["type"] == "agent" for r in data["results"])

    def test_search_with_types_query(self, client):
        headers = self._auth_headers(client)
        with database:
            Agent.create(hostname="typed-host", os="linux", username="root", status="online")
        resp = client.get("/api/v1/search?q=typed-host&types=agent", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["type"] == "agent" for r in data["results"])

    def test_search_unauthorized(self, client):
        resp = client.get("/api/v1/search?q=anything")
        assert resp.status_code == 401
