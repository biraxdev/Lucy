"""
Defense API — SIEM-style ingestion, authorized scanning, and detection alerts.

All endpoints are for authorized internal defensive operations only.
"""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.audit_logger import log_event
from database import database
from db.models import Agent, Task
from dependencies import CurrentUser, OperatorUser
from defense.detection_engine import DetectionEngine
from defense.scanners import SCANNERS
from core.task_queue import TaskQueue

router = APIRouter(prefix="/defense", tags=["defense"])
engine = DetectionEngine()
tq = TaskQueue()


class IngestEventRequest(BaseModel):
    source: str = "sensor"
    hostname: str
    event_type: str
    details: dict = {}
    severity: str = "info"
    mitre: Optional[str] = None


class IngestBulkRequest(BaseModel):
    events: list[dict]


class ScanRequest(BaseModel):
    agent_id: str
    scanner: str = Field(..., description="One of: port_scan, file_integrity, process_anomaly")
    action: str = "scan"
    params: dict = {}
    priority: str = "normal"


class DispatchScanRequest(BaseModel):
    scanner: str
    action: str = "scan"
    params: dict = {}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status")
async def defense_status(current_user: CurrentUser) -> dict:
    return {
        "mode": "defensive",
        "platform": "Lucy Defense Platform",
        "version": "1.0.0",
        "stats": engine.stats(),
    }


# ---------------------------------------------------------------------------
# Event ingestion
# ---------------------------------------------------------------------------

@router.post("/events", status_code=201)
async def ingest_event(
    body: IngestEventRequest, current_user: OperatorUser
) -> dict:
    event = engine.ingest(body.model_dump(exclude_none=True))
    log_event(
        action="defense_event_ingested",
        actor=current_user.get("username", "unknown"),
        resource_type="event",
        resource_id=event["id"],
        details={"event_type": body.event_type, "hostname": body.hostname},
    )
    return event


@router.post("/events/bulk", status_code=201)
async def ingest_events_bulk(
    body: IngestBulkRequest, current_user: OperatorUser
) -> dict:
    ingested = engine.ingest_bulk(body.events)
    return {"ingested": len(ingested)}


@router.get("/events")
async def list_events(
    current_user: CurrentUser,
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = Query(None),
    hostname: Optional[str] = Query(None),
) -> list[dict]:
    return engine.list_events(limit=limit, event_type=event_type, hostname=hostname)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.get("/alerts")
async def list_alerts(
    current_user: CurrentUser,
    limit: int = Query(100, ge=1, le=1000),
    severity: Optional[str] = Query(None),
    unread_only: bool = Query(False),
) -> list[dict]:
    return engine.list_alerts(limit=limit, severity=severity, unread_only=unread_only)


@router.get("/alerts/unread")
async def unread_alert_count(current_user: CurrentUser) -> dict:
    return {"count": engine.unread_alert_count()}


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, current_user: OperatorUser) -> dict:
    if not engine.mark_alert_read(alert_id):
        raise HTTPException(404, "Alert not found")
    return {"ok": True}


@router.post("/alerts/read-all")
async def mark_all_alerts_read(current_user: OperatorUser) -> dict:
    return {"marked": engine.mark_all_alerts_read()}


# ---------------------------------------------------------------------------
# Detection rules
# ---------------------------------------------------------------------------

@router.get("/rules")
async def list_rules(current_user: CurrentUser) -> list[dict]:
    return engine.get_rules()


@router.get("/mitre-map")
async def mitre_map(current_user: CurrentUser) -> dict:
    """Return a mapping of active detection rules to MITRE ATT&CK techniques."""
    mapping: dict[str, list[str]] = {}
    for rule in engine.get_rules():
        mitre = rule.get("mitre")
        if mitre:
            mapping.setdefault(mitre, []).append(rule["name"])
    return {"mapping": mapping, "rule_count": len(engine.get_rules())}


# ---------------------------------------------------------------------------
# Authorized scanning
# ---------------------------------------------------------------------------

@router.get("/scanners")
async def list_scanners(current_user: CurrentUser) -> list[dict]:
    return [
        {"id": k, "name": k.replace("_", " ").title(), "description": v.__doc__.strip().splitlines()[0] if v.__doc__ else ""}
        for k, v in SCANNERS.items()
    ]


@router.post("/scanners/run")
async def run_local_scan(body: DispatchScanRequest, current_user: OperatorUser) -> dict:
    """Run a defensive scanner directly on the Lucy backend host (authorized only)."""
    scanner = SCANNERS.get(body.scanner)
    if not scanner:
        raise HTTPException(400, f"Unknown scanner: {body.scanner}")
    try:
        result = scanner(action=body.action, **body.params)
        log_event(
            action="defense_scan_run",
            actor=current_user.get("username", "unknown"),
            resource_type="scan",
            resource_id=body.scanner,
            details={"scanner": body.scanner, "action": body.action, "params": body.params},
        )
        return result
    except Exception as exc:
        raise HTTPException(500, f"Scanner failed: {exc}") from exc


@router.post("/scanners/dispatch", status_code=201)
async def dispatch_sensor_scan(body: ScanRequest, current_user: OperatorUser) -> dict:
    """Dispatch a defensive scan task to a registered endpoint sensor."""
    agent = Agent.get_or_none(Agent.id == body.agent_id)
    if not agent:
        raise HTTPException(404, "Endpoint sensor not found")
    if body.scanner not in SCANNERS:
        raise HTTPException(400, f"Unknown scanner: {body.scanner}")

    task = await tq.enqueue(
        agent_id=body.agent_id,
        module=body.scanner,
        action=body.action,
        params=body.params,
        priority=body.priority,
    )
    log_event(
        action="defense_scan_dispatched",
        actor=current_user.get("username", "unknown"),
        resource_type="task",
        resource_id=str(task.id),
        details={"agent_id": body.agent_id, "scanner": body.scanner},
    )
    return task.to_dict()
