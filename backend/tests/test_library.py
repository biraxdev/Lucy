"""Resource Library API tests."""
import uuid

from config import settings


def _login(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_library_stats(client):
    token = _login(client)
    resp = client.get(
        "/api/v1/library/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_resources" in data
    assert "by_type" in data
    assert isinstance(data["total_resources"], int)


def test_library_list(client):
    token = _login(client)
    resp = client.get(
        "/api/v1/library",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


def test_library_create_get_delete(client):
    token = _login(client)
    name = f"pytest-snippet-{uuid.uuid4().hex[:8]}"

    create = client.post(
        "/api/v1/library",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "resource_type": "snippet",
            "name": name,
            "description": "Created by the Phase 1 test suite",
            "content": "print('lucy test')",
            "language": "python",
            "status": "draft",
            "visibility": "internal",
            "tags": ["test"],
        },
    )
    assert create.status_code == 201
    resource = create.json()
    assert "id" in resource
    rid = resource["id"]

    get = client.get(
        f"/api/v1/library/{rid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get.status_code == 200
    assert get.json()["id"] == rid
    assert get.json()["name"] == name

    delete = client.delete(
        f"/api/v1/library/{rid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete.status_code == 200
    assert delete.json().get("deleted") is True
    assert delete.json().get("id") == rid
