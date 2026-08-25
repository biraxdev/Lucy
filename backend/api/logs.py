from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.log_manager import LogManager
from db.models import Log
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/logs", tags=["logs"])
lm = LogManager()


class LogPush(BaseModel):
    level: str = "INFO"
    message: str
    module: str = "system"
    agent_id: str | None = None
    log_type: str = "system"


@router.get("")
async def list_logs(
    current_user: CurrentUser,
    agent_id: str | None = Query(None),
    level: str | None = Query(None),
    log_type: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0),
) -> list[dict]:
    q = Log.select().order_by(Log.timestamp.desc())
    if agent_id:
        q = q.where(Log.agent_id == agent_id)
    if level:
        q = q.where(Log.level == level.upper())
    if log_type:
        q = q.where(Log.log_type == log_type)
    if search:
        q = q.where(Log.message.contains(search))
    return [{"id": str(l.id), "agent_id": l.agent_id, "level": l.level, "module": l.module,
             "message": l.message, "log_type": l.log_type, "timestamp": str(l.timestamp)}
            for l in q.offset(offset).limit(limit)]


@router.post("", status_code=201)
async def push_log(body: LogPush, current_user: OperatorUser) -> dict:
    lm.push(body.level, body.message, body.module, body.agent_id, body.log_type)
    return {"status": "queued"}


@router.delete("")
async def clear_logs(current_user: OperatorUser) -> dict:
    n = Log.delete().execute()
    return {"deleted": n}
