"""Library API tests — tests for the REST endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    """Get auth headers for the admin user."""
    from main import app
    from core.auth import create_access_token
    token = create_access_token("admin", "superadmin", tenant_id=None)
    return {"Authorization": f"Bearer {token}"}


class TestLibraryAPI:
    """Tests for the /api/v1/library endpoints."""

    def test_list_resources(self, client, auth_headers):
        """GET /library should return a paginated list."""
        resp = client.get("/api/v1/library", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)

    def test_search_resources(self, client, auth_headers):
        """GET /library/search should return search results."""
        resp = client.get("/api/v1/library/search", params={"q": "test"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "query" in data

    def test_list_types(self, client, auth_headers):
        """GET /library/types should return type counts."""
        resp = client.get("/api/v1/library/types", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "types" in data
        assert isinstance(data["types"], dict)

    def test_list_tags(self, client, auth_headers):
        """GET /library/tags should return a list of tags."""
        resp = client.get("/api/v1/library/tags", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)

    def test_create_and_delete_resource(self, client, auth_headers):
        """POST /library should create a native resource, DELETE should remove it."""
        # Create
        resp = client.post("/api/v1/library", json={
            "resource_type": "snippet",
            "name": "Test Note",
            "content": "Test content",
            "tags": ["test"],
        }, headers=auth_headers)
        assert resp.status_code == 201
        resource = resp.json()
        assert resource["name"] == "Test Note"
        resource_id = resource["id"]

        # Get
        resp = client.get(f"/api/v1/library/{resource_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Note"

        # Update
        resp = client.patch(f"/api/v1/library/{resource_id}", json={
            "description": "Updated description",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

        # Delete
        resp = client.delete(f"/api/v1/library/{resource_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get(f"/api/v1/library/{resource_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_preview(self, client, auth_headers):
        """GET /library/{id}/preview should return a preview."""
        # Create a resource first
        resp = client.post("/api/v1/library", json={
            "resource_type": "snippet",
            "name": "Preview Test",
            "content": "Preview content",
        }, headers=auth_headers)
        resource_id = resp.json()["id"]

        # Get preview
        resp = client.get(f"/api/v1/library/{resource_id}/preview", headers=auth_headers)
        assert resp.status_code == 200

        # Cleanup
        client.delete(f"/api/v1/library/{resource_id}", headers=auth_headers)

    def test_favorite_toggle(self, client, auth_headers):
        """POST /library/{id}/favorite should toggle favorite."""
        resp = client.post("/api/v1/library", json={
            "resource_type": "snippet",
            "name": "Fav Test",
        }, headers=auth_headers)
        resource_id = resp.json()["id"]

        resp = client.post(f"/api/v1/library/{resource_id}/favorite", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["favorite"] == True

        resp = client.post(f"/api/v1/library/{resource_id}/favorite", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["favorite"] == False

        client.delete(f"/api/v1/library/{resource_id}", headers=auth_headers)

    def test_version_create_and_list(self, client, auth_headers):
        """POST /library/{id}/versions should create a version, GET should list it."""
        resp = client.post("/api/v1/library", json={
            "resource_type": "snippet",
            "name": "Version Test",
            "content": "v1 content",
        }, headers=auth_headers)
        resource_id = resp.json()["id"]

        # Create version
        resp = client.post(f"/api/v1/library/{resource_id}/versions", json={
            "change_note": "Initial version",
        }, headers=auth_headers)
        assert resp.status_code == 201

        # List versions
        resp = client.get(f"/api/v1/library/{resource_id}/versions", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["versions"]) >= 1

        client.delete(f"/api/v1/library/{resource_id}", headers=auth_headers)

    def test_duplicate_resource(self, client, auth_headers):
        """POST /library/{id}/duplicate should create a copy."""
        resp = client.post("/api/v1/library", json={
            "resource_type": "snippet",
            "name": "Dup Original",
            "content": "Content to duplicate",
        }, headers=auth_headers)
        resource_id = resp.json()["id"]

        resp = client.post(f"/api/v1/library/{resource_id}/duplicate", headers=auth_headers)
        assert resp.status_code == 201
        assert "copy" in resp.json()["name"].lower()

        # Cleanup both
        client.delete(f"/api/v1/library/{resp.json()['id']}", headers=auth_headers)
        client.delete(f"/api/v1/library/{resource_id}", headers=auth_headers)

    def test_export_resource(self, client, auth_headers):
        """GET /library/{id}/export should return exportable content."""
        resp = client.post("/api/v1/library", json={
            "resource_type": "snippet",
            "name": "Export Test",
            "content": "Export me",
        }, headers=auth_headers)
        resource_id = resp.json()["id"]

        resp = client.get(f"/api/v1/library/{resource_id}/export", params={"format": "json"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "name" in data

        client.delete(f"/api/v1/library/{resource_id}", headers=auth_headers)

    def test_suggestions(self, client, auth_headers):
        """GET /library/suggestions/{id} should return suggestions."""
        resp = client.post("/api/v1/library", json={
            "resource_type": "snippet",
            "name": "Suggestion Test",
        }, headers=auth_headers)
        resource_id = resp.json()["id"]

        resp = client.get(f"/api/v1/library/suggestions/{resource_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "suggestions" in resp.json()

        client.delete(f"/api/v1/library/{resource_id}", headers=auth_headers)

    def test_get_resource_not_found(self, client, auth_headers):
        """GET /library/{nonexistent} should return 404."""
        resp = client.get("/api/v1/library/nonexistent-uuid", headers=auth_headers)
        assert resp.status_code == 404
