"""
Operator presence and multi-player collaboration API.
GET  /operators/online   — list currently connected operators
POST /operators/presence — update operator presence (page, cursor)
GET  /operators/stats    — operator activity stats
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from datetime import datetime, timezone

from core.ws_manager import ConnectionManager
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/operators", tags=["operators"])
manager = ConnectionManager()


class PresenceUpdate(BaseModel):
    page: str = ""
    cursor: str = ""


@router.get("/online")
async def online_operators(current_user: CurrentUser = None) -> list[dict]:
    """List all currently connected operators with presence info."""
    return manager.get_online_operators()


@router.post("/presence")
async def update_presence(
    body: PresenceUpdate,
    current_user: OperatorUser = None,
) -> dict:
    """Update the current operator's presence (page, cursor)."""
    user_id = current_user.get("id", "") if isinstance(current_user, dict) else str(current_user)
    await manager.update_operator_presence(user_id, page=body.page, cursor=body.cursor)
    return {"ok": True}


@router.get("/stats")
async def operator_stats(current_user: CurrentUser = None) -> dict:
    """Return operator collaboration stats."""
    operators = manager.get_online_operators()
    return {
        "online_count": len(operators),
        "operators": operators,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/broadcast")
async def broadcast_to_operators(
    body: dict,
    current_user: OperatorUser = None,
) -> dict:
    """Broadcast a custom message to all connected operators."""
    from core.ws_manager import build_message
    msg = build_message("operator_broadcast", {
        "from": current_user.get("username", "unknown") if isinstance(current_user, dict) else "unknown",
        "message": body.get("message", ""),
        "channel": body.get("channel", "global"),
    })
    await manager.broadcast_to_frontends(msg)
    return {"ok": True, "delivered_to": len(manager.get_online_operators())}
