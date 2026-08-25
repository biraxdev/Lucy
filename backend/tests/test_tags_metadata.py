"""
Tests for the tag and metadata system on agents and credentials.

Run:
    cd backend
    pytest tests/test_tags_metadata.py -v
"""
import json
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def client():
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "testpass123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def sample_agent(client, auth_headers):
    """Create a minimal agent directly in the database."""
    from db.models import Agent
    from database import database

    with database:
        agent = Agent.create(
            hostname="tag-test-host",
            os="windows",
            username="testuser",
            status="online",
            public_key="test-key",
            tags='["windows", "domain_joined"]',
            metadata='{"department": "IT", "role": "workstation"}',
        )
    return str(agent.id)


@pytest.fixture
def sample_credential(client, auth_headers, sample_agent):
    """Create a minimal credential directly in the database."""
    from db.models import Credential
    from database import database

    with database:
        cred = Credential.create(
            agent=sample_agent,
            source="browser",
            url="https://example.com",
            username="admin",
            password_encrypted="cGFzc3dvcmQ=",
            confidence="high",
            tags='["domain_admin", "weak"]',
            metadata='{"domain": "example.com", "mfa": false}',
        )
    return str(cred.id)


# ---------------------------------------------------------------------------
# TagManager unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_normalize_tags():
    from core.tag_manager import TagManager

    tm = TagManager()
    assert tm._normalize_tags(["Foo", "BAR", "foo", "  baz  "]) == ["bar", "baz", "foo"]
    assert tm._normalize_tags("one, two,three") == ["one", "three", "two"]
    assert tm._normalize_tags(None) == []


@pytest.mark.asyncio
async def test_agent_tag_operations(client, sample_agent):
    from core.tag_manager import TagManager

    tm = TagManager()
    result = tm.add_tags("agent", sample_agent, ["high_priv", "windows"])
    assert sorted(result["tags"]) == ["domain_joined", "high_priv", "windows"]

    result = tm.remove_tags("agent", sample_agent, ["high_priv"])
    assert sorted(result["tags"]) == ["domain_joined", "windows"]

    result = tm.set_tags("agent", sample_agent, ["linux", "server"])
    assert sorted(result["tags"]) == ["linux", "server"]


@pytest.mark.asyncio
async def test_agent_metadata_operations(client, sample_agent):
    from core.tag_manager import TagManager

    tm = TagManager()
    result = tm.update_metadata("agent", sample_agent, {"location": "datacenter1"})
    assert result["metadata"]["location"] == "datacenter1"
    assert result["metadata"]["department"] == "IT"

    result = tm.set_metadata("agent", sample_agent, {"owner": "redteam"})
    assert result["metadata"] == {"owner": "redteam"}


@pytest.mark.asyncio
async def test_filter_by_tags(client, sample_agent):
    from core.tag_manager import TagManager

    tm = TagManager()
    results = tm.filter_by_tags("agent", ["domain_joined"])
    assert len(results) >= 1
    assert any(r["id"] == sample_agent for r in results)

    results = tm.filter_by_tags("agent", ["domain_joined", "windows"], match_all=True)
    assert any(r["id"] == sample_agent for r in results)


@pytest.mark.asyncio
async def test_filter_by_metadata(client, sample_agent):
    from core.tag_manager import TagManager

    tm = TagManager()
    results = tm.filter_by_metadata("agent", {"department": "IT"})
    assert any(r["id"] == sample_agent for r in results)


@pytest.mark.asyncio
async def test_credential_ingest_with_tags_and_metadata(client, sample_agent):
    from uuid import uuid4
    from core.credential_manager import CredentialManager

    cm = CredentialManager()
    unique = uuid4().hex[:8]
    result = cm.ingest(
        sample_agent,
        "browser",
        [
            {
                "url": f"https://corp-{unique}.com",
                "username": f"jdoe-{unique}",
                "password": "secret123",
                "tags": ["vpn", "weak"],
                "metadata": {"domain": f"corp-{unique}.com", "mfa": True},
            }
        ],
    )
    assert result["new"] == 1
    assert result["ingested"] == 1


# ---------------------------------------------------------------------------
# REST API tests
# ---------------------------------------------------------------------------


def test_list_agents_with_tag_filter(client, auth_headers, sample_agent):
    resp = client.get("/api/v1/agents?tags=windows", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert any(a["id"] == sample_agent for a in data)

    resp = client.get("/api/v1/agents?tags=domain_joined,windows", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert any(a["id"] == sample_agent for a in data)


def test_list_agents_with_metadata_filter(client, auth_headers, sample_agent):
    resp = client.get(
        '/api/v1/agents?metadata={"department":"IT"}',
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(a["id"] == sample_agent for a in data)


def test_add_and_remove_agent_tags(client, auth_headers, sample_agent):
    resp = client.post(
        f"/api/v1/agents/{sample_agent}/tags",
        json={"tags": ["high_priv"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "high_priv" in resp.json()["tags"]

    resp = client.request(
        "DELETE",
        f"/api/v1/agents/{sample_agent}/tags",
        json={"tags": ["high_priv"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "high_priv" not in resp.json()["tags"]


def test_merge_agent_metadata(client, auth_headers, sample_agent):
    resp = client.patch(
        f"/api/v1/agents/{sample_agent}/metadata",
        json={"metadata": {"location": "site-a"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["metadata"]["location"] == "site-a"
    assert resp.json()["metadata"]["department"] == "IT"


def test_bulk_agent_tags(client, auth_headers, sample_agent):
    resp = client.post(
        "/api/v1/agents/bulk/tags?mode=add",
        json={"ids": [sample_agent], "tags": ["bulk-tag"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1

    resp = client.get("/api/v1/agents", headers=auth_headers)
    data = resp.json()
    agent = next(a for a in data if a["id"] == sample_agent)
    assert "bulk-tag" in agent["tags"]


def test_search_credentials_with_tags(client, auth_headers, sample_credential):
    resp = client.get(
        "/api/v1/credentials?tags=domain_admin",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(c["id"] == sample_credential for c in data)


def test_search_credentials_with_metadata(client, auth_headers, sample_credential):
    resp = client.get(
        '/api/v1/credentials?metadata={"domain":"example.com"}',
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(c["id"] == sample_credential for c in data)


def test_add_and_remove_credential_tags(client, auth_headers, sample_credential):
    resp = client.post(
        f"/api/v1/credentials/{sample_credential}/tags",
        json={"tags": ["finance"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "finance" in resp.json()["tags"]

    resp = client.request(
        "DELETE",
        f"/api/v1/credentials/{sample_credential}/tags",
        json={"tags": ["finance"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "finance" not in resp.json()["tags"]


def test_unique_tags_endpoint(client, auth_headers, sample_agent, sample_credential):
    resp = client.get("/api/v1/agents/tags/unique", headers=auth_headers)
    assert resp.status_code == 200
    assert "windows" in resp.json()

    resp = client.get("/api/v1/credentials/tags/unique", headers=auth_headers)
    assert resp.status_code == 200
    assert "domain_admin" in resp.json()
