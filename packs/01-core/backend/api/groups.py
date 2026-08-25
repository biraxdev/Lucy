import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.group_manager import GroupManager
from database import database
from db.models import Agent, AgentGroup
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/groups", tags=["groups"])
gm = GroupManager()


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    members: list[str] = []
    dynamic_query: str = ""
    color: str = "#22c55e"


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    members: list[str] | None = None
    dynamic_query: str | None = None
    color: str | None = None


class BulkMembers(BaseModel):
    agent_ids: list[str] = Field(..., min_length=1)


@router.get("")
async def list_groups(current_user: CurrentUser) -> list[dict]:
    return gm.list_groups()


@router.post("", status_code=201)
async def create_group(body: GroupCreate, current_user: OperatorUser) -> dict:
    group = gm.create_group(
        name=body.name,
        description=body.description,
        members=body.members,
        dynamic_query=body.dynamic_query or None,
        color=body.color,
    )
    return group.to_dict()


@router.get("/{group_id}")
async def get_group(group_id: str, current_user: CurrentUser) -> dict:
    g = gm.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    return g.to_dict()


@router.put("/{group_id}")
async def update_group(group_id: str, body: GroupUpdate, current_user: OperatorUser) -> dict:
    g = gm.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    g = gm.update_group(group_id, **updates)
    return g.to_dict()


@router.post("/{group_id}/members")
async def add_member(group_id: str, body: dict, current_user: OperatorUser) -> dict:
    agent_id = body.get("agent_id")
    if not agent_id:
        raise HTTPException(400, "agent_id required")
    g = gm.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    g = gm.add_member(group_id, agent_id)
    return g.to_dict()


@router.post("/{group_id}/members/bulk")
async def add_members_bulk(group_id: str, body: BulkMembers, current_user: OperatorUser) -> dict:
    """Add multiple agents to a group in a single call (for 50+ agent fleets)."""
    g = gm.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    members = json.loads(g.members or "[]")
    added = 0
    for aid in body.agent_ids:
        if aid not in members:
            members.append(aid)
            added += 1
    with database:
        AgentGroup.update(members=json.dumps(members)).where(AgentGroup.id == group_id).execute()
    return gm.get_group(group_id).to_dict()


@router.delete("/{group_id}/members/bulk")
async def remove_members_bulk(group_id: str, body: BulkMembers, current_user: OperatorUser) -> dict:
    """Remove multiple agents from a group in a single call."""
    g = gm.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    remove_set = set(body.agent_ids)
    members = [m for m in json.loads(g.members or "[]") if m not in remove_set]
    with database:
        AgentGroup.update(members=json.dumps(members)).where(AgentGroup.id == group_id).execute()
    return gm.get_group(group_id).to_dict()


@router.delete("/{group_id}/members/{agent_id}")
async def remove_member(group_id: str, agent_id: str, current_user: OperatorUser) -> dict:
    g = gm.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    g = gm.remove_member(group_id, agent_id)
    return g.to_dict()


@router.get("/{group_id}/resolve")
async def resolve_group(group_id: str, current_user: CurrentUser) -> dict:
    g = gm.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    members = gm.resolve_members(group_id)
    return {"group_id": group_id, "members": members, "count": len(members)}


@router.get("/{group_id}/summary")
async def group_summary(group_id: str, current_user: CurrentUser) -> dict:
    """
    Return a health summary for a group: total/online/idle/offline counts,
    OS distribution, and last-active timestamp. Designed for 50+ agent fleets.
    """
    g = gm.get_group(group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    member_ids = set(gm.resolve_members(group_id))
    if not member_ids:
        return {
            "group_id": group_id,
            "name": g.name,
            "total": 0, "online": 0, "idle": 0, "offline": 0,
            "os_distribution": {}, "last_active": None,
        }
    with database:
        agents = list(Agent.select().where(Agent.id.in_(list(member_ids))))
    total = len(agents)
    online = sum(1 for a in agents if a.status == "online")
    idle = sum(1 for a in agents if a.status == "idle")
    offline = sum(1 for a in agents if a.status not in ("online", "idle"))
    os_dist: dict[str, int] = {}
    last_active = None
    for a in agents:
        os_dist[a.os] = os_dist.get(a.os, 0) + 1
        if a.last_seen and (last_active is None or a.last_seen > last_active):
            last_active = a.last_seen
    return {
        "group_id": group_id,
        "name": g.name,
        "total": total,
        "online": online,
        "idle": idle,
        "offline": offline,
        "os_distribution": os_dist,
        "last_active": last_active.isoformat() if last_active else None,
    }


@router.get("/agent/{agent_id}")
async def groups_for_agent(agent_id: str, current_user: CurrentUser) -> list[dict]:
    """Return all groups that contain the given agent (static or dynamic)."""
    result: list[dict] = []
    with database:
        for g in AgentGroup.select():
            members = gm.resolve_members(g.id)
            if agent_id in members:
                result.append(g.to_dict())
    return result


@router.get("/summaries/all")
async def all_group_summaries(current_user: CurrentUser) -> list[dict]:
    """Return health summaries for all groups in one call (dashboard-friendly)."""
    summaries: list[dict] = []
    for g in gm.list_groups():
        member_ids = set(gm.resolve_members(g["id"]))
        if not member_ids:
            summaries.append({
                "group_id": g["id"], "name": g["name"], "color": g.get("color", "#22c55e"),
                "total": 0, "online": 0, "idle": 0, "offline": 0,
                "os_distribution": {}, "last_active": None,
                "is_dynamic": bool(g.get("dynamic_query")),
            })
            continue
        with database:
            agents = list(Agent.select().where(Agent.id.in_(list(member_ids))))
        online = sum(1 for a in agents if a.status == "online")
        idle = sum(1 for a in agents if a.status == "idle")
        offline = sum(1 for a in agents if a.status not in ("online", "idle"))
        os_dist: dict[str, int] = {}
        last_active = None
        for a in agents:
            os_dist[a.os] = os_dist.get(a.os, 0) + 1
            if a.last_seen and (last_active is None or a.last_seen > last_active):
                last_active = a.last_seen
        summaries.append({
            "group_id": g["id"], "name": g["name"], "color": g.get("color", "#22c55e"),
            "total": len(agents), "online": online, "idle": idle, "offline": offline,
            "os_distribution": os_dist,
            "last_active": last_active.isoformat() if last_active else None,
            "is_dynamic": bool(g.get("dynamic_query")),
        })
    return summaries


@router.delete("/{group_id}", status_code=204)
async def delete_group(group_id: str, current_user: OperatorUser) -> None:
    if not gm.delete_group(group_id):
        raise HTTPException(404, "Group not found")
