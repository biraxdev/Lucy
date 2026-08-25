"""
Alerts API for Project Lucy.
GET  /alerts          — list recent alerts
POST /alerts/read     — mark alert(s) read
GET  /alerts/unread   — unread count
GET  /alerts/webhooks — list webhooks
POST /alerts/webhooks — add webhook
DELETE /alerts/webhooks/{id} — remove webhook
POST /alerts/webhooks/{id}/test — send test alert
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.alert_manager import AlertManager
from core.predictive_alerting import PredictiveAlertEngine
from dependencies import CurrentUser, OperatorUser

import json

router = APIRouter(prefix="/alerts", tags=["alerts"])
alerts = AlertManager()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MarkReadBody(BaseModel):
    alert_ids: list[str] | None = None   # None = mark all


class WebhookBody(BaseModel):
    name: str
    url: str
    kind: str = "generic"   # slack | discord | generic
    enabled: bool = True
    min_severity: str = "info"
    events: list[str] = []  # empty = all events
    secret: str = ""
    username: str = ""
    avatar_url: str = ""
    template: str | None = None  # optional Jinja2 JSON payload override


class RenderTemplateBody(BaseModel):
    template: str
    kind: str = "generic"
    username: str = ""
    avatar_url: str = ""


# ---------------------------------------------------------------------------
# Alert feed
# ---------------------------------------------------------------------------

@router.get("")
async def list_alerts(
    limit: int = 100,
    unread_only: bool = False,
    current_user: CurrentUser = None,
) -> list[dict]:
    return alerts.get_alerts(limit=limit, unread_only=unread_only)


@router.get("/unread")
async def unread_count(current_user: CurrentUser = None) -> dict:
    return {"count": alerts.unread_count()}


@router.post("/read")
async def mark_read(body: MarkReadBody, current_user: CurrentUser = None) -> dict:
    if body.alert_ids is None:
        count = alerts.mark_all_read()
        return {"marked": count}
    count = 0
    for aid in body.alert_ids:
        if alerts.mark_read(aid):
            count += 1
    return {"marked": count}


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

@router.get("/webhooks")
async def list_webhooks(current_user: OperatorUser = None) -> list[dict]:
    return alerts.get_webhooks()


@router.post("/webhooks", status_code=201)
async def add_webhook(body: WebhookBody, current_user: OperatorUser = None) -> dict:
    webhook = alerts.add_webhook(body.model_dump())
    return webhook


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def remove_webhook(webhook_id: str, current_user: OperatorUser = None) -> None:
    if not alerts.remove_webhook(webhook_id):
        raise HTTPException(404, "Webhook not found")


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: str, current_user: OperatorUser = None) -> dict:
    webhook = next((w for w in alerts.get_webhooks() if w["id"] == webhook_id), None)
    if not webhook:
        raise HTTPException(404, "Webhook not found")
    test_alert = {
        "id": "test-00000000",
        "event": "test",
        "title": "Lucy C2 — Webhook Test",
        "message": "This is a test alert from Lucy C2. Your webhook is configured correctly.",
        "severity": "info",
        "agent_id": None,
        "data": {},
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    try:
        from core.alert_manager import _send_webhook
        await _send_webhook(webhook, test_alert)
        return {"ok": True, "message": "Test webhook delivered successfully"}
    except Exception as exc:
        raise HTTPException(400, f"Webhook delivery failed: {exc}")


@router.post("/webhooks/{webhook_id}/render")
async def render_webhook_template(webhook_id: str, body: RenderTemplateBody, current_user: OperatorUser = None) -> dict:
    """Preview the rendered JSON payload for a webhook template without sending it."""
    webhook = next((w for w in alerts.get_webhooks() if w["id"] == webhook_id), None)
    if not webhook:
        raise HTTPException(404, "Webhook not found")

    from core.alert_manager import _build_payload

    preview_alert = {
        "id": "preview-00000000",
        "event": "preview",
        "title": "Lucy C2 — Template Preview",
        "message": "This is a preview of your custom webhook template.",
        "severity": "warning",
        "agent_id": "preview-agent",
        "data": {"sample": True},
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }

    preview_webhook = {
        **webhook,
        "kind": body.kind,
        "username": body.username or webhook.get("username", ""),
        "avatar_url": body.avatar_url or webhook.get("avatar_url", ""),
        "template": body.template,
    }

    try:
        payload = _build_payload(preview_webhook, preview_alert)
        return {"ok": True, "payload": payload}
    except Exception as exc:
        raise HTTPException(400, f"Template render failed: {exc}")


# ---------------------------------------------------------------------------
# Manual fire (for testing / custom alerts)
# ---------------------------------------------------------------------------

class FireAlertBody(BaseModel):
    event: str = "custom"
    title: str
    message: str
    severity: str = "info"
    agent_id: str | None = None
    data: dict = {}


@router.post("/fire", status_code=201)
async def fire_alert(body: FireAlertBody, current_user: OperatorUser = None) -> dict:
    alert = await alerts.fire(
        event=body.event,
        title=body.title,
        message=body.message,
        severity=body.severity,
        agent_id=body.agent_id,
        data=body.data,
    )
    return alert


# ---------------------------------------------------------------------------
# Predictive alerting
# ---------------------------------------------------------------------------

engine = PredictiveAlertEngine()


@router.get("/predictions")
async def list_predictions(
    limit: int = 100,
    active_only: bool = False,
    current_user: CurrentUser = None,
) -> dict:
    """Return predictions generated by the historical-analysis engine."""
    if active_only:
        return {"predictions": engine.get_active_threats()[:limit]}
    return {"predictions": engine.get_predictions(limit=limit)}


@router.post("/predictions/run")
async def run_predictions(current_user: OperatorUser = None) -> dict:
    """Force a predictive analysis cycle now."""
    predictions = await engine.run_analysis()
    return {"ran": True, "generated": len(predictions)}


# ---------------------------------------------------------------------------
# Circular action: convert an alert into a dispatched task
# ---------------------------------------------------------------------------

class AlertToTaskBody(BaseModel):
    module: str = "shell"
    action: str = "run"
    params: dict = {}
    priority: str = "high"


@router.post("/{alert_id}/to-task", status_code=201)
async def alert_to_task(
    alert_id: str,
    body: AlertToTaskBody,
    current_user: OperatorUser = None,
) -> dict:
    """
    Convert an alert into a task dispatched to the alert's agent.
    Closes the reactive loop: alert → task → result → resolution.
    """
    import uuid as _uuid
    from database import database
    from db.models import Task

    alert = next((a for a in alerts.get_alerts(limit=500) if a.get("id") == alert_id), None)
    if not alert:
        raise HTTPException(404, "Alert not found")

    agent_id = alert.get("agent_id")
    if not agent_id:
        raise HTTPException(400, "Alert has no associated agent — cannot dispatch task")

    with database:
        task = Task.create(
            id=str(_uuid.uuid4()),
            agent=agent_id,
            module=body.module,
            action=body.action,
            params=json.dumps(body.params),
            status="queued",
            priority=body.priority,
        )

    # Dispatch via WS if agent is connected
    try:
        from core.ws_manager import ConnectionManager, build_message
        manager = ConnectionManager()
        msg = build_message("task", {
            "task_id": str(task.id),
            "module": body.module,
            "action": body.action,
            "params": body.params,
            "timeout": 60,
        }, agent_id=str(agent_id))
        conn = manager.agents.get(str(agent_id))
        if conn:
            await conn.send(msg)
    except Exception:
        pass

    # Mark alert as read
    alerts.mark_read(alert_id)

    return {
        "task_id": str(task.id),
        "alert_id": alert_id,
        "agent_id": str(agent_id),
        "status": "queued",
        "message": f"Task {body.module}/{body.action} dispatched to agent {str(agent_id)[:8]} from alert",
    }
