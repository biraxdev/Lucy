"""Tests for the Prometheus /metrics endpoint."""
import pytest
from fastapi.testclient import TestClient


def test_metrics_endpoint(client: TestClient) -> None:
    """The metrics endpoint should be public and return Prometheus text."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "lucy_agents_total" in body
    assert "lucy_tasks_total" in body
    assert "lucy_library_resources_total" in body


def test_metrics_tracks_requests(client: TestClient) -> None:
    """A request to an API endpoint should be reflected in the counter."""
    # Warm the counter by making an authenticated request first.
    auth = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
