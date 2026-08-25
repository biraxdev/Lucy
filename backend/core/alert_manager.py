"""
Alert Manager for Project Lucy.
Manages in-memory alert feed, persists to DB, and dispatches webhooks
(Slack, Discord, generic HTTP) for critical events.

Events fired automatically:
  - agent_connect    : new agent connected
  - agent_disconnect : agent went offline
  - credential_found : new credential harvested
  - task_failed      : task returned failed status
  - timeline_done    : timeline completed
  - custom           : manual / arbitrary alert
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

try:
    from jinja2 import Environment, BaseLoader, TemplateError
except ImportError:  # pragma: no cover
    Environment = BaseLoader = TemplateError = None  # type: ignore

logger = logging.getLogger(__name__)

# In-memory circular buffer — last 500 alerts
_MAX_ALERTS = 500


class AlertManager:
    """Singleton alert manager."""

    _instance: Optional["AlertManager"] = None

    def __new__(cls) -> "AlertManager":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._alerts: list[dict] = []
            inst._webhooks: list[dict] = []   # runtime webhook configs
            inst._lock = asyncio.Lock()
            cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fire(
        self,
        event: str,
        title: str,
        message: str,
        severity: str = "info",       # info | warning | critical
        agent_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> dict:
        alert = {
            "id": str(uuid.uuid4()),
            "event": event,
            "title": title,
            "message": message,
            "severity": severity,
            "agent_id": agent_id,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }

        async with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > _MAX_ALERTS:
                self._alerts = self._alerts[-_MAX_ALERTS:]

        self._persist(alert)
        asyncio.create_task(self._broadcast_ws(alert))
        asyncio.create_task(self._dispatch_webhooks(alert))

        logger.info("[ALERT][%s] %s — %s", severity.upper(), title, message)
        return alert

    def get_alerts(self, limit: int = 100, unread_only: bool = False) -> list[dict]:
        alerts = list(reversed(self._alerts))
        if unread_only:
            alerts = [a for a in alerts if not a.get("read")]
        return alerts[:limit]

    def mark_read(self, alert_id: str) -> bool:
        for a in self._alerts:
            if a["id"] == alert_id:
                a["read"] = True
                return True
        return False

    def mark_all_read(self) -> int:
        count = 0
        for a in self._alerts:
            if not a["read"]:
                a["read"] = True
                count += 1
        return count

    def unread_count(self) -> int:
        return sum(1 for a in self._alerts if not a.get("read"))

    def add_webhook(self, webhook: dict) -> dict:
        webhook = {**webhook, "id": webhook.get("id") or str(uuid.uuid4())}
        self._webhooks = [w for w in self._webhooks if w["id"] != webhook["id"]]
        self._webhooks.append(webhook)
        self._save_webhooks()
        return webhook

    def remove_webhook(self, webhook_id: str) -> bool:
        before = len(self._webhooks)
        self._webhooks = [w for w in self._webhooks if w["id"] != webhook_id]
        self._save_webhooks()
        return len(self._webhooks) < before

    def get_webhooks(self) -> list[dict]:
        return list(self._webhooks)

    def load_webhooks_from_db(self) -> None:
        try:
            from db.models import AlertWebhook
            from database import database
            with database:
                for w in AlertWebhook.select():
                    self._webhooks.append(w.to_dict())
        except Exception as exc:
            logger.debug("Could not load webhooks from DB: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self, alert: dict) -> None:
        try:
            from database import database
            from db.models import AlertEvent
            with database:
                AlertEvent.create(
                    id=alert["id"],
                    event=alert["event"],
                    title=alert["title"],
                    message=alert["message"],
                    severity=alert["severity"],
                    agent_id=alert.get("agent_id"),
                    data=json.dumps(alert.get("data", {})),
                    timestamp=datetime.fromisoformat(alert["timestamp"]),
                )
        except Exception as exc:
            logger.debug("Alert persist failed: %s", exc)

    async def _broadcast_ws(self, alert: dict) -> None:
        try:
            from core.ws_manager import ConnectionManager, build_message
            manager = ConnectionManager()
            await manager.broadcast_to_frontends(
                build_message("alert", alert)
            )
        except Exception as exc:
            logger.debug("Alert WS broadcast failed: %s", exc)

    async def _dispatch_webhooks(self, alert: dict) -> None:
        for webhook in list(self._webhooks):
            if not webhook.get("enabled", True):
                continue
            min_severity = webhook.get("min_severity", "info")
            if not _severity_passes(alert["severity"], min_severity):
                continue
            event_filter = webhook.get("events")
            if event_filter and alert["event"] not in event_filter:
                continue
            try:
                await _send_webhook(webhook, alert)
            except Exception as exc:
                logger.warning("Webhook '%s' failed: %s", webhook.get("url"), exc)

    def _save_webhooks(self) -> None:
        try:
            from database import database
            from db.models import AlertWebhook
            with database:
                AlertWebhook.delete().execute()
                for w in self._webhooks:
                    AlertWebhook.create(
                        id=w["id"],
                        name=w.get("name", ""),
                        url=w["url"],
                        kind=w.get("kind", "generic"),
                        enabled=w.get("enabled", True),
                        min_severity=w.get("min_severity", "info"),
                        events=json.dumps(w.get("events") or []),
                        secret=w.get("secret", ""),
                        template=w.get("template"),
                    )
        except Exception as exc:
            logger.debug("Webhook save failed: %s", exc)


# ---------------------------------------------------------------------------
# Webhook dispatcher
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


def _severity_passes(event_sev: str, min_sev: str) -> bool:
    return _SEVERITY_ORDER.get(event_sev, 0) >= _SEVERITY_ORDER.get(min_sev, 0)


_SEVERITY_COLORS = {
    "info":     3447003,   # blue
    "warning":  16776960,  # yellow
    "critical": 15158332,  # red
}
_SEVERITY_EMOJI = {
    "info": "ℹ️",
    "warning": "⚠️",
    "critical": "🚨",
}


# Default Jinja2 templates for each webhook kind.
_DEFAULT_TEMPLATES: dict[str, str] = {
    "slack": """{
  "username": "{{ username | default('Lucy C2') }}",
  "icon_emoji": "{{ icon_emoji | default(':shield:') }}",
  "attachments": [{
    "color": "{{ color }}",
    "title": "{{ emoji }} {{ title }}",
    "text": "{{ message }}",
    "fields": [
      {"title": "Severity", "value": "{{ severity.upper() }}", "short": true},
      {"title": "Event", "value": "{{ event }}", "short": true},
      {"title": "Agent", "value": "{{ agent_id or '—' }}", "short": true},
      {"title": "Time", "value": "{{ timestamp[:19].replace('T', ' ') }}", "short": true}
    ],
    "footer": "Lucy C2 Alert System",
    "ts": {{ ts }}
  }]
}""",
    "discord": """{
  "username": "{{ username | default('Lucy C2') }}",
  "avatar_url": "{{ avatar_url | default('') }}",
  "embeds": [{
    "title": "{{ emoji }} {{ title }}",
    "description": "{{ message }}",
    "color": {{ color }},
    "fields": [
      {"name": "Severity", "value": "`{{ severity.upper() }}`", "inline": true},
      {"name": "Event", "value": "`{{ event }}`", "inline": true},
      {"name": "Agent", "value": "`{{ agent_id or '—' }}`", "inline": true}
    ],
    "footer": {"text": "Lucy C2 Alert System"},
    "timestamp": "{{ timestamp }}"
  }]
}""",
    "generic": """{
  "id": "{{ id }}",
  "event": "{{ event }}",
  "title": "{{ title }}",
  "message": "{{ message }}",
  "severity": "{{ severity }}",
  "agent_id": {{ agent_id | tojson }},
  "data": {{ data | tojson }},
  "timestamp": "{{ timestamp }}"
}""",
}


async def _send_webhook(webhook: dict, alert: dict) -> None:
    url = webhook["url"]
    timeout = httpx.Timeout(8.0)
    payload = _build_payload(webhook, alert)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        logger.debug("Webhook '%s' delivered (HTTP %d)", url, resp.status_code)


def _build_payload(webhook: dict, alert: dict) -> dict:
    """Build the webhook payload, optionally using a custom Jinja2 template."""
    kind = webhook.get("kind", "generic")
    custom_template = webhook.get("template")

    if custom_template and Environment is not None:
        try:
            return _render_template(custom_template, webhook, alert)
        except TemplateError:
            logger.warning("Invalid custom template for webhook '%s', falling back to default", webhook.get("name"))
        except Exception as exc:
            logger.warning("Custom template render failed: %s", exc)

    default_template = _DEFAULT_TEMPLATES.get(kind, _DEFAULT_TEMPLATES["generic"])
    return _render_template(default_template, webhook, alert)


def _render_template(template_str: str, webhook: dict, alert: dict) -> dict:
    """Render a Jinja2 template string into a JSON payload dict."""
    if Environment is None:
        raise RuntimeError("Jinja2 is not installed")

    env = Environment(loader=BaseLoader())
    template = env.from_string(template_str)

    ctx = {
        # alert fields
        "id": alert["id"],
        "event": alert["event"],
        "title": alert["title"],
        "message": alert["message"],
        "severity": alert["severity"],
        "agent_id": alert.get("agent_id"),
        "data": alert.get("data", {}),
        "timestamp": alert["timestamp"],
        "ts": int(datetime.fromisoformat(alert["timestamp"]).timestamp()),
        # computed helpers
        "emoji": _SEVERITY_EMOJI.get(alert["severity"], "🔔"),
        "color": _SEVERITY_COLORS.get(alert["severity"], 6710886) if webhook.get("kind") == "discord" else
                 {"info": "#3b82f6", "warning": "#f59e0b", "critical": "#ef4444"}.get(alert["severity"], "#6b7280"),
        # webhook fields
        "username": webhook.get("username", "Lucy C2"),
        "icon_emoji": webhook.get("icon_emoji", ":shield:"),
        "avatar_url": webhook.get("avatar_url", ""),
        "name": webhook.get("name", ""),
        "url": webhook.get("url", ""),
    }

    rendered = template.render(**ctx)
    return json.loads(rendered)


def _build_slack_payload(webhook: dict, alert: dict) -> dict:
    """Legacy helper kept for compatibility."""
    return _build_payload(webhook, alert)


def _build_discord_payload(webhook: dict, alert: dict) -> dict:
    """Legacy helper kept for compatibility."""
    return _build_payload(webhook, alert)


def _build_generic_payload(alert: dict) -> dict:
    """Legacy helper kept for compatibility."""
    return _build_payload({"kind": "generic"}, alert)
