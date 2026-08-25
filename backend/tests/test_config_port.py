"""
Tests for configuration export/import endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from database import database
from db.models import AgentGroup, Module, Timeline


@pytest.fixture(autouse=True)
def clean_config_data():
    with database:
        Timeline.delete().execute()
        AgentGroup.delete().execute()
        Module.delete().execute()
    yield


class TestConfigPortAPI:
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

    def _seed_data(self):
        with database:
            Timeline.create(
                name="Recon",
                description="Basic recon",
                agent_group='["all"]',
                steps='[{"order":1,"module":"info","action":"run","params":{}}]',
                trigger="manual",
                loop=False,
                status="draft",
            )
            AgentGroup.create(name="Alpha", description="Alpha team", type="static", members='[]', color="#ff0000")
            Module.create(
                name="custom_module",
                version="1.0.0",
                code="def run(**kwargs): return {}",
                description="A custom module",
                signature="sig",
                enabled=True,
            )

    def test_export_all(self, client):
        headers = self._auth_headers(client)
        self._seed_data()
        resp = client.get("/api/v1/config/export", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "timelines" in data
        assert "groups" in data
        assert "modules" in data
        assert any(t["name"] == "Recon" for t in data["timelines"])
        assert any(g["name"] == "Alpha" for g in data["groups"])
        assert any(m["name"] == "custom_module" for m in data["modules"])

    def test_export_filtered(self, client):
        headers = self._auth_headers(client)
        self._seed_data()
        resp = client.get("/api/v1/config/export?types=groups", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["types"] == ["groups"]
        assert "groups" in data
        assert "timelines" not in data
        assert "modules" not in data

    def test_import_new(self, client):
        headers = self._auth_headers(client)
        payload = {
            "config": {
                "timelines": [
                    {"name": "Exfil", "description": "Exfil timeline", "steps": [], "trigger": "manual", "status": "draft"}
                ],
                "groups": [
                    {"name": "Bravo", "description": "Bravo team", "type": "static", "members": [], "color": "#00ff00"}
                ],
                "modules": [
                    {"name": "imported_mod", "version": "1.0.0", "code": "def run(): pass", "enabled": True}
                ],
            },
            "strategy": "skip",
        }
        resp = client.post("/api/v1/config/import", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "Exfil" in data["imported"]["timelines"]
        assert "Bravo" in data["imported"]["groups"]
        assert "imported_mod" in data["imported"]["modules"]

    def test_import_skip_existing(self, client):
        headers = self._auth_headers(client)
        self._seed_data()
        payload = {
            "config": {
                "modules": [
                    {"name": "custom_module", "version": "2.0.0", "code": "changed", "enabled": True}
                ]
            },
            "strategy": "skip",
        }
        resp = client.post("/api/v1/config/import", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "custom_module" in data["skipped"]["modules"]
        with database:
            mod = Module.get(Module.name == "custom_module")
        assert mod.version == "1.0.0"  # unchanged

    def test_import_overwrite(self, client):
        headers = self._auth_headers(client)
        self._seed_data()
        payload = {
            "config": {
                "modules": [
                    {"name": "custom_module", "version": "2.0.0", "code": "changed", "enabled": True}
                ]
            },
            "strategy": "overwrite",
        }
        resp = client.post("/api/v1/config/import", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "custom_module" in data["imported"]["modules"]
        with database:
            mod = Module.get(Module.name == "custom_module")
        assert mod.version == "2.0.0"

    def test_import_unauthorized(self, client):
        resp = client.post("/api/v1/config/import", json={"config": {}})
        assert resp.status_code == 401

    def test_export_unauthorized(self, client):
        resp = client.get("/api/v1/config/export")
        assert resp.status_code == 401
