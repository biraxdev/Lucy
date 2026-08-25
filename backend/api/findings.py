"""
Findings API for Project Lucy.
CRUD for manually managed security findings + circular finding-to-task action.
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import database
from db.models import Finding, Task
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/findings", tags=["findings"])


class FindingBody(BaseModel):
    title: str
    severity: str = "high"        # critical|high|medium|low|info
    status: str = "draft"         # draft|reviewed|accepted|mitigated|false_positive
    description: str = ""
    recommendation: str = ""
    evidence: str = ""
    cvss: float | None = None
    agent_id: str | None = None


@router.get("")
async def list_findings(current_user: CurrentUser = None) -> list[dict]:
    with database:
        return [f.to_dict() for f in Finding.select().order_by(Finding.created_at.desc())]


@router.post("", status_code=201)
async def create_finding(body: FindingBody, current_user: OperatorUser = None) -> dict:
    with database:
        f = Finding.create(
            id=str(uuid.uuid4()),
            title=body.title,
            severity=body.severity,
            status=body.status,
            description=body.description,
            recommendation=body.recommendation,
            evidence=body.evidence,
            cvss=body.cvss,
            agent_id=body.agent_id,
        )
    return f.to_dict()


@router.get("/{finding_id}")
async def get_finding(finding_id: str, current_user: CurrentUser = None) -> dict:
    with database:
        f = Finding.get_or_none(Finding.id == finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    return f.to_dict()


@router.patch("/{finding_id}")
async def update_finding(finding_id: str, body: FindingBody, current_user: OperatorUser = None) -> dict:
    with database:
        f = Finding.get_or_none(Finding.id == finding_id)
        if not f:
            raise HTTPException(404, "Finding not found")
        update_data = body.model_dump(exclude_unset=True)
        if "cvss" in update_data:
            update_data["cvss"] = str(update_data["cvss"]) if update_data["cvss"] is not None else None
        update_data["updated_at"] = datetime.now(timezone.utc)
        Finding.update(**update_data).where(Finding.id == finding_id).execute()
        f = Finding.get_or_none(Finding.id == finding_id)
    return f.to_dict()


@router.delete("/{finding_id}", status_code=204)
async def delete_finding(finding_id: str, current_user: OperatorUser = None) -> None:
    with database:
        deleted = Finding.delete().where(Finding.id == finding_id).execute()
    if not deleted:
        raise HTTPException(404, "Finding not found")


# ---------------------------------------------------------------------------
# Circular action: convert a finding into an actionable task
# ---------------------------------------------------------------------------

class FindingToTaskBody(BaseModel):
    module: str = "shell"
    action: str = "run"
    params: dict = {}
    priority: str = "normal"


@router.post("/{finding_id}/to-task", status_code=201)
async def finding_to_task(
    finding_id: str,
    body: FindingToTaskBody,
    current_user: OperatorUser = None,
) -> dict:
    """
    Convert a finding into a task dispatched to the finding's agent.
    This closes the loop: finding → task → result → updated finding.
    """
    with database:
        f = Finding.get_or_none(Finding.id == finding_id)
        if not f:
            raise HTTPException(404, "Finding not found")
        if not f.agent_id:
            raise HTTPException(400, "Finding has no associated agent — cannot dispatch task")

        task = Task.create(
            id=str(uuid.uuid4()),
            agent=f.agent_id,
            module=body.module,
            action=body.action,
            params=json.dumps(body.params),
            status="queued",
            priority=body.priority,
        )

        # Link the finding to the task for traceability
        Finding.update(
            status="reviewed",
            updated_at=datetime.now(timezone.utc),
        ).where(Finding.id == finding_id).execute()

    # Notify the agent via WS if connected
    try:
        from core.ws_manager import ConnectionManager, build_message
        manager = ConnectionManager()
        msg = build_message("task", {
            "task_id": str(task.id),
            "module": body.module,
            "action": body.action,
            "params": body.params,
            "timeout": 60,
        }, agent_id=str(f.agent_id))
        conn = manager.agents.get(str(f.agent_id))
        if conn:
            await conn.send(msg)
    except Exception:
        pass  # Task is queued; agent will pick it up on next heartbeat

    return {
        "task_id": str(task.id),
        "finding_id": str(finding_id),
        "agent_id": str(f.agent_id),
        "status": "queued",
        "message": f"Task {body.module}/{body.action} dispatched to agent {f.agent_id} from finding {finding_id[:8]}",
    }
