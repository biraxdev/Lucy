import base64
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from config import settings
from core.audit_logger import log_event
from core.crypto import server_handshake
from core.tag_manager import TagManager
from database import database
from api.tasks import tq
from db.models import Agent, AgentGroup, Task
from dependencies import CurrentUser, OperatorUser, limiter

tag_manager = TagManager()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AgentRegisterRequest(BaseModel):
    hostname: str
    os: str
    username: str
    ip_private: str | None = None
    ip_public: str | None = None
    architecture: str | None = None
    processor: str | None = None
    ram_total: int | None = None
    ram_available: int | None = None
    public_key: str = Field(..., description="PEM-encoded ECDH P-256 public key")
    tags: list[str] = []
    metadata: dict | None = None


class AgentRegisterResponse(BaseModel):
    agent_id: str
    public_key: str
    nonce: str
    nonce_encrypted: str


class HeartbeatRequest(BaseModel):
    agent_id: str
    cpu: float = 0.0
    ram_available: int = 0
    status: str = "online"


class AgentUpdateRequest(BaseModel):
    status: str | None = None
    group_id: str | None = None
    tags: list[str] | None = None
    metadata: dict | None = None


class AgentSelfUpdateRequest(BaseModel):
    url: str | None = None
    version: str | None = None
    force: bool = False
    checksum: str | None = None


class PullModuleRequest(BaseModel):
    version: str | None = None
    force: bool = False


class BulkTagRequest(BaseModel):
    ids: list[str]
    tags: list[str]


class BulkMetadataRequest(BaseModel):
    ids: list[str]
    metadata: dict
    merge: bool = True


# ---------------------------------------------------------------------------
# POST /api/v1/agents/register  — no auth required (agent self-registration)
# ---------------------------------------------------------------------------


@router.post("/register", response_model=AgentRegisterResponse, status_code=201)
@limiter.limit("10/minute")
async def register_agent(body: AgentRegisterRequest, request: Request) -> AgentRegisterResponse:
    """
    Agent registration + ECDH handshake.
    Returns server public key + nonce proof for AES key derivation.
    """
    agent_public_key_pem = body.public_key.encode("utf-8")

    try:
        hs = server_handshake(agent_public_key_pem)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Handshake failed: {exc}",
        ) from exc

    aes_key_b64 = base64.b64encode(hs.aes_key).decode("utf-8")

    existing = Agent.get_or_none(
        (Agent.hostname == body.hostname) & (Agent.username == body.username)
    )

    with database:
        if existing:
            Agent.update(
                status="online",
                last_seen=datetime.now(timezone.utc),
                ip_public=body.ip_public,
                ip_private=body.ip_private,
                ram_total=body.ram_total,
                ram_available=body.ram_available,
                public_key=body.public_key,
                aes_key=aes_key_b64,
                tags=json.dumps(body.tags),
                metadata=json.dumps(body.metadata) if body.metadata else None,
            ).where(Agent.id == existing.id).execute()
            agent_id = str(existing.id)
        else:
            agent = Agent.create(
                hostname=body.hostname,
                os=body.os,
                username=body.username,
                ip_public=body.ip_public,
                ip_private=body.ip_private,
                architecture=body.architecture,
                processor=body.processor,
                ram_total=body.ram_total,
                ram_available=body.ram_available,
                status="online",
                public_key=body.public_key,
                aes_key=aes_key_b64,
                tags=json.dumps(body.tags),
                metadata=json.dumps(body.metadata) if body.metadata else None,
            )
            agent_id = str(agent.id)

    return AgentRegisterResponse(
        agent_id=agent_id,
        public_key=hs.server_public_key_pem.decode("utf-8"),
        nonce=hs.nonce_b64,
        nonce_encrypted=hs.nonce_encrypted_b64,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/agents/{agent_id}/heartbeat  — no auth (agent)
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/heartbeat")
@limiter.limit("60/minute")
async def agent_heartbeat(agent_id: str, body: HeartbeatRequest, request: Request) -> dict:
    """Receive heartbeat from agent, return pending tasks.

    Also re-queues stale 'running' tasks that were dispatched via WS
    but never completed (agent disconnected before sending result).
    """
    from db.models import Task

    with database:
        Agent.update(
            status=body.status,
            last_seen=datetime.now(timezone.utc),
            ram_available=body.ram_available,
        ).where(Agent.id == agent_id).execute()

        # Re-queue stale running tasks (dispatched via WS but agent
        # disconnected before completing). 2-minute timeout.
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
        stale = list(
            Task.select()
            .where(
                (Task.agent == agent_id)
                & (Task.status == "running")
                & (Task.executed_at < stale_cutoff)
            )
        )
        for t in stale:
            Task.update(status="queued").where(Task.id == t.id).execute()
            logger.info("Re-queued stale running task %s for agent %s", t.id, agent_id)

        pending = list(
            Task.select()
            .where((Task.agent == agent_id) & (Task.status == "queued"))
            .order_by(Task.created_at)
            .limit(10)
        )

        task_list = []
        for t in pending:
            task_list.append({
                "task_id": str(t.id),
                "module": t.module,
                "action": t.action,
                "params": t.params_dict,
                "timeout": 60,
            })
            Task.update(status="running").where(Task.id == t.id).execute()

    return {"tasks": task_list}


# ---------------------------------------------------------------------------
# POST /api/v1/tasks/{task_id}/result  — no auth (agent)
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/result")
async def agent_result(agent_id: str, body: dict) -> dict:
    """Receive task result from agent (HTTP polling fallback)."""
    from db.models import Task

    task_id = body.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id required")

    with database:
        Task.update(
            status=body.get("status", "completed"),
            result=json.dumps(body.get("data")),
            error=body.get("error"),
            executed_at=datetime.now(timezone.utc),
        ).where(Task.id == task_id).execute()

    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /api/v1/agents/{agent_id}/kill  — operator
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/kill")
async def kill_agent(agent_id: str, current_user: OperatorUser) -> dict:
    """Mark the agent offline and drop its connection (operator kill button)."""
    from core.ws_manager import ConnectionManager

    agent = Agent.get_or_none(Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    with database:
        Agent.update(
            status="offline",
            last_seen=datetime.now(timezone.utc),
        ).where(Agent.id == agent_id).execute()
    try:
        await ConnectionManager().disconnect_agent(agent_id, reason="killed")
    except Exception:
        pass
    return {"ok": True, "agent_id": agent_id, "status": "offline"}


# ---------------------------------------------------------------------------
# GET /api/v1/agents  — operator
# ---------------------------------------------------------------------------
# GET /api/v1/agents  — operator
# ---------------------------------------------------------------------------


@router.get("")
async def list_agents(
    current_user: CurrentUser,
    status: str | None = None,
    tags: str | None = None,
    metadata: str | None = None,
    match_all_tags: bool = True,
) -> list[dict]:
    """List agents with optional status, tag, and metadata filters."""

    query = Agent.select().order_by(Agent.last_seen.desc())
    if status:
        query = query.where(Agent.status == status)

    agents = [a.to_dict() for a in query]

    if tags:
        target_tags = [t.strip().lower() for t in tags.split(",") if t.strip()]
        if target_tags:
            if match_all_tags:
                agents = [
                    a for a in agents
                    if all(t in [x.lower() for x in a.get("tags", [])] for t in target_tags)
                ]
            else:
                agents = [
                    a for a in agents
                    if any(t in [x.lower() for x in a.get("tags", [])] for t in target_tags)
                ]

    if metadata:
        try:
            metadata_query = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        if metadata_query:
            agents = [
                a for a in agents
                if all(a.get("metadata", {}).get(k) == v for k, v in metadata_query.items())
            ]

    return agents


# ---------------------------------------------------------------------------
# GET /api/v1/agents/{agent_id}
# ---------------------------------------------------------------------------


@router.get("/{agent_id}")
async def get_agent(agent_id: str, current_user: CurrentUser) -> dict:
    agent = Agent.get_or_none(Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()


# ---------------------------------------------------------------------------
# PATCH /api/v1/agents/{agent_id}
# ---------------------------------------------------------------------------


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str, body: AgentUpdateRequest, current_user: OperatorUser
) -> dict:
    agent = Agent.get_or_none(Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    updates: dict = {}
    if body.status is not None:
        updates["status"] = body.status
    if body.group_id is not None:
        group = AgentGroup.get_or_none(AgentGroup.id == body.group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        updates["group"] = body.group_id
    if body.tags is not None:
        updates["tags"] = json.dumps(body.tags)
    if body.metadata is not None:
        updates["metadata"] = json.dumps(body.metadata)

    if updates:
        with database:
            Agent.update(**updates).where(Agent.id == agent_id).execute()
        agent = Agent.get_by_id(agent_id)

    return agent.to_dict()


# ---------------------------------------------------------------------------
# POST /api/v1/agents/{agent_id}/update  — operator
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/update", status_code=201)
async def request_agent_update(
    agent_id: str,
    body: AgentSelfUpdateRequest,
    current_user: OperatorUser,
) -> dict:
    """Request the agent to auto-update to a new version/package."""
    agent = Agent.get_or_none(Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    with database:
        task = Task.create(
            agent=agent_id,
            module="agent_update",
            action="update",
            params=json.dumps({
                "url": body.url,
                "version": body.version,
                "force": body.force,
                "checksum": body.checksum,
            }),
            priority="high",
            timeout=300,
            status="queued",
        )
    return {"ok": True, "task_id": str(task.id), "message": "Agent update requested"}


# ---------------------------------------------------------------------------
# POST /api/v1/agents/{agent_id}/pull-module/{module_name}  — operator
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/pull-module/{module_name}", status_code=201)
async def request_pull_module(
    agent_id: str,
    module_name: str,
    body: PullModuleRequest,
    current_user: OperatorUser,
) -> dict:
    """Request the agent to pull a module from the backend module store."""
    agent = Agent.get_or_none(Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from core.module_manager import ModuleManager

    manager = ModuleManager()
    mod = manager.get(module_name)
    if not mod:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    with database:
        task = Task.create(
            agent=agent_id,
            module="module_pull",
            action="pull",
            params=json.dumps({
                "module_name": module_name,
                "version": body.version or mod.version,
                "force": body.force,
                "download_url": f"/api/v1/modules/{module_name}/download",
            }),
            priority="high",
            timeout=120,
            status="queued",
        )
    return {"ok": True, "task_id": str(task.id), "message": f"Module pull requested: {module_name}"}


# ---------------------------------------------------------------------------
# GET /api/v1/agents/{agent_id}/update-status  — operator
# ---------------------------------------------------------------------------


@router.get("/{agent_id}/update-status")
async def get_agent_update_status(agent_id: str, current_user: CurrentUser) -> dict:
    """Return recent agent_update and module_pull tasks for this agent."""
    agent = Agent.get_or_none(Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    with database:
        tasks = list(
            Task.select()
            .where(
                (Task.agent == agent_id)
                & (Task.module.in_(["agent_update", "module_pull"]))
            )
            .order_by(Task.created_at.desc())
            .limit(20)
        )

    return {
        "agent_id": agent_id,
        "tasks": [t.to_dict() for t in tasks],
    }


class TagOperationRequest(BaseModel):
    tags: list[str]


class MetadataOperationRequest(BaseModel):
    metadata: dict


# ---------------------------------------------------------------------------
# POST /api/v1/agents/bulk/tags  — operator (before /{agent_id}/tags)
# ---------------------------------------------------------------------------


@router.post("/bulk/tags")
async def bulk_update_agent_tags(
    body: BulkTagRequest,
    current_user: OperatorUser,
    mode: str = "add",
) -> dict:
    """Bulk add, set, or remove tags on agents."""
    if mode not in {"add", "set", "remove"}:
        raise HTTPException(status_code=400, detail="mode must be add, set, or remove")
    try:
        if mode == "add":
            return tag_manager.bulk_add_tags("agent", body.ids, body.tags)
        if mode == "set":
            return tag_manager.bulk_set_tags("agent", body.ids, body.tags)
        return tag_manager.bulk_remove_tags("agent", body.ids, body.tags)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# POST /api/v1/agents/bulk/metadata  — operator (before /{agent_id}/metadata)
# ---------------------------------------------------------------------------


@router.post("/bulk/metadata")
async def bulk_update_agent_metadata(
    body: BulkMetadataRequest,
    current_user: OperatorUser,
) -> dict:
    """Bulk merge or replace metadata on agents."""
    try:
        if body.merge:
            return tag_manager.bulk_update_metadata("agent", body.ids, body.metadata)
        return tag_manager.bulk_set_metadata("agent", body.ids, body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# POST/DELETE /api/v1/agents/{agent_id}/tags  — operator
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/tags")
async def add_agent_tags(
    agent_id: str, body: TagOperationRequest, current_user: OperatorUser
) -> dict:
    try:
        return tag_manager.add_tags("agent", agent_id, body.tags)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{agent_id}/tags")
async def remove_agent_tags(
    agent_id: str, body: TagOperationRequest, current_user: OperatorUser
) -> dict:
    try:
        return tag_manager.remove_tags("agent", agent_id, body.tags)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# PUT/PATCH /api/v1/agents/{agent_id}/metadata  — operator
# ---------------------------------------------------------------------------


@router.put("/{agent_id}/metadata")
async def set_agent_metadata(
    agent_id: str, body: MetadataOperationRequest, current_user: OperatorUser
) -> dict:
    try:
        return tag_manager.set_metadata("agent", agent_id, body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{agent_id}/metadata")
async def merge_agent_metadata(
    agent_id: str, body: MetadataOperationRequest, current_user: OperatorUser
) -> dict:
    try:
        return tag_manager.update_metadata("agent", agent_id, body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /api/v1/agents/tags  — operator
# ---------------------------------------------------------------------------


@router.get("/tags/unique")
async def list_agent_tags(current_user: CurrentUser) -> list[str]:
    """Return all unique tags across agents."""
    return tag_manager.get_unique_tags("agent")


# ---------------------------------------------------------------------------
# DELETE /api/v1/agents/{agent_id}  — admin
# ---------------------------------------------------------------------------


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, current_user: CurrentUser) -> None:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    deleted = Agent.delete().where(Agent.id == agent_id).execute()
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")


# ---------------------------------------------------------------------------
# POST /api/v1/agents/{agent_id}/mode  — set agent mode
# ---------------------------------------------------------------------------


class AgentModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(dormant|living|dead)$")


@router.post("/{agent_id}/mode", status_code=201)
async def set_agent_mode(
    agent_id: str,
    body: AgentModeRequest,
    current_user: OperatorUser,
) -> dict:
    """Enqueue a builtin/set_mode task for the agent."""
    agent = Agent.get_or_none(Agent.id == agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    task = await tq.enqueue(
        agent_id=agent_id,
        module="builtin",
        action="set_mode",
        params={"mode": body.mode},
        priority="high",
        timeout=60,
    )
    log_event(
        action="agent_mode_set",
        actor=current_user.get("username", "unknown"),
        resource_type="agent",
        resource_id=agent_id,
        details={"mode": body.mode, "task_id": str(task.id)},
    )
    return {"agent_id": agent_id, "mode": body.mode, "task_id": str(task.id)}
