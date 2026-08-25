"""
File Events API for Project Lucy.
Tracks file operations performed by agents.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import database
from db.models import FileEvent, Agent
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/files", tags=["files"])


class FileEventCreate(BaseModel):
    agent_id: str
    path: str
    action: str           # upload | download | delete | modify | list
    size: int | None = None
    hash: str | None = None


@router.get("")
async def list_file_events(
    current_user: CurrentUser,
    agent_id: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0),
) -> list[dict]:
    q = FileEvent.select().order_by(FileEvent.timestamp.desc())
    if agent_id:
        q = q.where(FileEvent.agent == agent_id)
    if action:
        q = q.where(FileEvent.action == action)
    return [f.to_dict() for f in q.offset(offset).limit(limit)]


@router.post("", status_code=201)
async def create_file_event(body: FileEventCreate, current_user: OperatorUser) -> dict:
    if not Agent.get_or_none(Agent.id == body.agent_id):
        raise HTTPException(404, "Agent not found")
    with database:
        ev = FileEvent.create(
            agent=body.agent_id,
            path=body.path,
            action=body.action,
            size=body.size,
            hash=body.hash,
        )
    return ev.to_dict()


@router.delete("/{event_id}", status_code=204)
async def delete_file_event(event_id: str, current_user: OperatorUser) -> None:
    with database:
        n = FileEvent.delete().where(FileEvent.id == event_id).execute()
    if not n:
        raise HTTPException(404, "File event not found")


@router.get("/agent/{agent_id}/stats")
async def agent_file_stats(agent_id: str, current_user: CurrentUser) -> dict:
    events = FileEvent.select().where(FileEvent.agent == agent_id)
    by_action: dict[str, int] = {}
    total_size = 0
    for ev in events:
        by_action[ev.action] = by_action.get(ev.action, 0) + 1
        if ev.size:
            total_size += ev.size
    return {
        "agent_id": agent_id,
        "total_events": sum(by_action.values()),
        "by_action": by_action,
        "total_size_bytes": total_size,
    }
