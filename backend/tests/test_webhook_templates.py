"""
Tests for advanced webhooks with custom Jinja2 message templates.
"""
import pytest
from fastapi.testclient import TestClient

from core.alert_manager import _build_payload, _DEFAULT_TEMPLATES


ALERT = {
    "id": "alert-1",
    "event": "credential_found",
    "title": "New credential",
    "message": "Chrome credential found",
    "severity": "critical",
    "agent_id": "agent-abc",
    "data": {"source": "chrome"},
    "timestamp": "2026-07-04T12:00:00+00:00",
}


class TestWebhookTemplates:
    def test_default_slack_payload(self):
        webhook = {"kind": "slack", "name": "slack-1", "url": "https://hooks.slack.com/test"}
        payload = _build_payload(webhook, ALERT)
        assert payload["attachments"][0]["title"].startswith("🚨")
        assert payload["attachments"][0]["fields"][0]["value"] == "CRITICAL"

    def test_default_discord_payload(self):
        webhook = {"kind": "discord", "name": "discord-1", "url": "https://discord.com/api/webhooks/test"}
        payload = _build_payload(webhook, ALERT)
        assert payload["embeds"][0]["title"].startswith("🚨")
        assert payload["embeds"][0]["color"] == 15158332

    def test_default_generic_payload(self):
        webhook = {"kind": "generic", "name": "generic-1", "url": "https://example.com/webhook"}
        payload = _build_payload(webhook, ALERT)
        assert payload["event"] == "credential_found"
        assert payload["severity"] == "critical"
        assert payload["data"]["source"] == "chrome"

    def test_custom_template_override(self):
        custom = '{"event": "{{ event }}", "custom": "{{ title }}", "severity": "{{ severity }}"}'
        webhook = {"kind": "generic", "name": "custom-1", "url": "https://example.com/webhook", "template": custom}
        payload = _build_payload(webhook, ALERT)
        assert payload["event"] == "credential_found"
        assert payload["custom"] == "New credential"

    def test_custom_template_with_data_filter(self):
        custom = '{"source": "{{ data.source }}", "agent": "{{ agent_id }}"}'
        webhook = {"kind": "generic", "template": custom}
        payload = _build_payload(webhook, ALERT)
        assert payload["source"] == "chrome"
        assert payload["agent"] == "agent-abc"

    def test_invalid_template_falls_back_to_default(self):
        custom = "{not valid json"
        webhook = {"kind": "slack", "template": custom}
        payload = _build_payload(webhook, ALERT)
        assert "attachments" in payload

    def test_all_default_templates_are_valid_json(self):
        for kind, tmpl in _DEFAULT_TEMPLATES.items():
            webhook = {"kind": kind}
            payload = _build_payload(webhook, ALERT)
            assert isinstance(payload, dict)
            assert payload


class TestWebhookTemplateAPI:
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

    def test_create_webhook_with_template(self, client):
        headers = self._auth_headers(client)
        body = {
            "name": "custom-slack",
            "url": "https://hooks.slack.com/test",
            "kind": "slack",
            "template": '{"text": "{{ severity.upper() }}: {{ title }}"}',
        }
        resp = client.post("/api/v1/alerts/webhooks", json=body, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["template"] == body["template"]

    def test_render_webhook_template(self, client):
        headers = self._auth_headers(client)
        body = {
            "name": "render-test",
            "url": "https://example.com/webhook",
            "kind": "generic",
        }
        resp = client.post("/api/v1/alerts/webhooks", json=body, headers=headers)
        assert resp.status_code == 201
        webhook_id = resp.json()["id"]

        render_body = {
            "template": '{"event": "{{ event }}", "title": "{{ title }}", "severity": "{{ severity }}"}',
            "kind": "generic",
        }
        resp = client.post(f"/api/v1/alerts/webhooks/{webhook_id}/render", json=render_body, headers=headers)
        assert resp.status_code == 200
        payload = resp.json()["payload"]
        assert payload["event"] == "preview"
        assert payload["title"] == "Lucy C2 — Template Preview"
        assert payload["severity"] == "warning"
