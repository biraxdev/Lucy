import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.audit_logger import log_event
from core.task_queue import TaskQueue
from database import database
from db.models import Task
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/tasks", tags=["tasks"])
tq = TaskQueue()


class TaskCreate(BaseModel):
    agent_id: str
    module: str
    action: str = "run"
    params: dict = {}
    priority: str = "normal"
    timeout: int = 60
    timeline_id: str | None = None


class TaskUpdate(BaseModel):
    status: str


@router.get("")
async def list_tasks(
    current_user: CurrentUser,
    agent_id: str | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    tasks = tq.list_tasks(agent_id=agent_id, status=status, priority=priority, limit=limit, offset=offset)
    return [t.to_dict() for t in tasks]


@router.post("", status_code=201)
async def create_task(body: TaskCreate, current_user: OperatorUser) -> dict:
    task = await tq.enqueue(
        agent_id=body.agent_id,
        module=body.module,
        action=body.action,
        params=body.params,
        priority=body.priority,
        timeout=body.timeout,
        timeline_id=body.timeline_id,
    )
    try:
        log_event(
            action="task_created",
            actor=current_user.get("username", "unknown"),
            resource_type="task",
            resource_id=str(task.id),
            details={
                "agent_id": body.agent_id,
                "module": body.module,
                "action": body.action,
                "priority": body.priority,
            },
        )
    except Exception:
        pass
    return task.to_dict()


@router.post("/{task_id}/result")
async def submit_task_result(task_id: str, body: dict) -> dict:
    """Receive task result from agent (HTTP polling path). Mirrors agent_result."""
    from datetime import datetime, timezone

    task = Task.get_or_none(Task.id == task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task.status = body.get("status", "completed")
    try:
        task.result = json.dumps(body.get("data")) if body.get("data") is not None else None
    except Exception:
        task.result = str(body.get("data"))
    task.error = body.get("error")
    task.executed_at = datetime.now(timezone.utc)
    task.save()

    # Auto-generate findings from completed tasks
    if task.status in ("completed", "ok"):
        try:
            from core.finding_engine import generate_findings_from_task
            generate_findings_from_task(task)
        except Exception:
            pass

    return {"ok": True}


@router.get("/{task_id}")
async def get_task(task_id: str, current_user: CurrentUser) -> dict:
    task = Task.get_or_none(Task.id == task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task.to_dict()


@router.delete("/{task_id}", status_code=204)
async def cancel_task(task_id: str, current_user: OperatorUser) -> None:
    if not await tq.cancel(task_id):
        raise HTTPException(400, "Task cannot be cancelled")


@router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskUpdate, current_user: OperatorUser) -> dict:
    task = Task.get_or_none(Task.id == task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task.status = body.status
    task.save()
    return task.to_dict()


@router.get("/agent/{agent_id}/pending")
async def agent_pending_tasks(agent_id: str, current_user: CurrentUser) -> list[dict]:
    tasks = tq.list_tasks(agent_id=agent_id, status="queued")
    return [t.to_dict() for t in tasks]
