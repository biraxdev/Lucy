import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

from fastapi import WebSocket

from config import settings

logger = logging.getLogger(__name__)

_OFFLINE_QUEUE_MAX = 256

MessageHandler = Callable[[str, dict], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Message builder helpers
# ---------------------------------------------------------------------------


def build_message(
    msg_type: str,
    payload: dict,
    agent_id: str = "",
    task_id: str = "",
    hmac_key: Optional[bytes] = None,
) -> dict:
    """Construct a standardised WS message envelope."""
    msg: dict[str, Any] = {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if agent_id:
        msg["agent_id"] = agent_id
    if task_id:
        msg["task_id"] = task_id
    if hmac_key:
        import hashlib
        import hmac as _hmac

        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        msg["signature"] = _hmac.new(hmac_key, raw, hashlib.sha256).hexdigest()
    return msg


def verify_message_signature(msg: dict, hmac_key: bytes) -> bool:
    """Verify HMAC-SHA256 signature on an incoming message."""
    import hashlib
    import hmac as _hmac

    signature = msg.get("signature", "")
    payload = msg.get("payload", {})
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    expected = _hmac.new(hmac_key, raw, hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# AgentConnection
# ---------------------------------------------------------------------------


class AgentConnection:
    """WebSocket wrapper for a single agent — heartbeat tracking + offline queue."""

    def __init__(self, agent_id: str, websocket: WebSocket) -> None:
        self.agent_id = agent_id
        self.websocket = websocket
        self.connected_at = datetime.now(timezone.utc)
        self.last_heartbeat = datetime.now(timezone.utc)
        self._alive = True
        self._offline_queue: list[dict] = []
        self._subscribed_channels: set[str] = {f"agent:{agent_id}"}

    # --- Send ---

    async def send(self, message: dict) -> bool:
        """Send message; marks connection dead on failure. Returns success."""
        if not self._alive:
            self._enqueue_offline(message)
            return False
        try:
            await self.websocket.send_text(json.dumps(message))
            return True
        except Exception as exc:
            logger.warning("Send failed for agent %s: %s", self.agent_id, exc)
            self._alive = False
            self._enqueue_offline(message)
            return False

    async def send_ping(self) -> None:
        await self.send(
            {"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()}
        )

    # --- Offline queue ---

    def _enqueue_offline(self, message: dict) -> None:
        if len(self._offline_queue) < _OFFLINE_QUEUE_MAX:
            self._offline_queue.append(message)
        else:
            logger.debug(
                "Offline queue full for agent %s — dropping message.", self.agent_id
            )

    async def flush_offline_queue(self) -> int:
        """Flush queued messages after reconnect. Returns number sent."""
        sent = 0
        while self._offline_queue:
            msg = self._offline_queue.pop(0)
            if await self.send(msg):
                sent += 1
            else:
                break
        return sent

    # --- Heartbeat ---

    def touch(self) -> None:
        self.last_heartbeat = datetime.now(timezone.utc)
        self._alive = True

    def is_timed_out(self) -> bool:
        delta = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        return delta > settings.WS_HEARTBEAT_INTERVAL * 2

    # --- Channels ---

    def subscribe(self, channel: str) -> None:
        self._subscribed_channels.add(channel)

    def unsubscribe(self, channel: str) -> None:
        self._subscribed_channels.discard(channel)

    def is_subscribed(self, channel: str) -> bool:
        return channel in self._subscribed_channels


# ---------------------------------------------------------------------------
# FrontendConnection
# ---------------------------------------------------------------------------


class FrontendConnection:
    """WebSocket wrapper for an operator frontend session."""

    def __init__(self, user_id: str, websocket: WebSocket) -> None:
        self.user_id = user_id
        self.websocket = websocket
        self._alive = True
        self._subscribed_channels: set[str] = set()
        self.connected_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.username: str = ""
        self.role: str = "operator"
        self.current_page: str = ""
        self.cursor_position: str = ""

    async def send(self, message: dict) -> bool:
        if not self._alive:
            return False
        try:
            await self.websocket.send_text(json.dumps(message))
            return True
        except Exception:
            self._alive = False
            return False

    def subscribe(self, channel: str) -> None:
        self._subscribed_channels.add(channel)

    def unsubscribe(self, channel: str) -> None:
        self._subscribed_channels.discard(channel)

    def is_subscribed(self, channel: str) -> bool:
        return channel in self._subscribed_channels or "*" in self._subscribed_channels


# ---------------------------------------------------------------------------
# MessageRouter
# ---------------------------------------------------------------------------


class MessageRouter:
    """Routes incoming WS messages by type to registered async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[MessageHandler]] = defaultdict(list)

    def register(self, msg_type: str, handler: MessageHandler) -> None:
        self._handlers[msg_type].append(handler)

    async def route(self, agent_id: str, message: dict) -> None:
        msg_type = message.get("type", "unknown")
        handlers = self._handlers.get(msg_type, []) + self._handlers.get("*", [])
        if not handlers:
            logger.debug("No handler for message type '%s' from %s", msg_type, agent_id)
            return
        for handler in handlers:
            try:
                await handler(agent_id, message)
            except Exception as exc:
                logger.error(
                    "Handler error for type '%s' agent %s: %s", msg_type, agent_id, exc
                )


# ---------------------------------------------------------------------------
# ConnectionManager (singleton)
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Singleton broker — manages all agent and frontend WebSocket connections."""

    _instance: Optional["ConnectionManager"] = None

    def __new__(cls) -> "ConnectionManager":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._agents: dict[str, AgentConnection] = {}
            inst._frontends: list[FrontendConnection] = {}
            inst._router = MessageRouter()
            inst._keepalive_task: Optional[asyncio.Task] = None
            cls._instance = inst
        return cls._instance

    # --- Lifecycle ---

    async def start_keepalive(self) -> None:
        """Start background ping loop."""
        if self._keepalive_task is None or self._keepalive_task.done():
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            logger.info("WS keepalive loop started (interval: %ds).", settings.WS_HEARTBEAT_INTERVAL)

    async def stop_keepalive(self) -> None:
        if self._keepalive_task:
            self._keepalive_task.cancel()

    async def _keepalive_loop(self) -> None:
        while True:
            await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
            await self._ping_agents()
            await self._reap_timed_out_agents()

    async def _ping_agents(self) -> None:
        for conn in list(self._agents.values()):
            await conn.send_ping()

    async def _reap_timed_out_agents(self) -> None:
        timed_out = [
            aid for aid, conn in self._agents.items() if conn.is_timed_out()
        ]
        for agent_id in timed_out:
            logger.warning("Agent %s timed out — marking offline.", agent_id)
            await self.disconnect_agent(agent_id, reason="timeout")

    # --- Agent connections ---

    async def connect_agent(self, agent_id: str, websocket: WebSocket) -> AgentConnection:
        await websocket.accept()

        existing = self._agents.get(agent_id)
        offline_queue = existing._offline_queue if existing else []

        conn = AgentConnection(agent_id, websocket)
        conn._offline_queue = offline_queue
        self._agents[agent_id] = conn

        flushed = await conn.flush_offline_queue()
        if flushed:
            logger.info("Agent %s reconnected — flushed %d queued messages.", agent_id, flushed)
        else:
            logger.info("Agent %s connected.", agent_id)

        await self._sync_agent_status(agent_id, "online")
        await self.broadcast_to_frontends(
            build_message("agent_connected", {"agent_id": agent_id})
        )
        return conn

    async def disconnect_agent(self, agent_id: str, reason: str = "disconnect") -> None:
        self._agents.pop(agent_id, None)
        await self._sync_agent_status(agent_id, "offline")
        await self.broadcast_to_frontends(
            build_message("agent_disconnected", {"agent_id": agent_id, "reason": reason})
        )
        logger.info("Agent %s disconnected (%s).", agent_id, reason)

    # --- Frontend connections ---

    async def connect_frontend(self, user_id: str, websocket: WebSocket, username: str = "", role: str = "operator") -> FrontendConnection:
        await websocket.accept()
        conn = FrontendConnection(user_id, websocket)
        conn.username = username
        conn.role = role
        conn.subscribe("*")
        if not isinstance(self._frontends, list):
            self._frontends = []
        self._frontends.append(conn)
        logger.info("Frontend user %s (%s) connected.", username or user_id, role)
        # Broadcast operator presence to all frontends
        await self.broadcast_to_frontends(
            build_message("operator_connected", {
                "user_id": user_id,
                "username": username,
                "role": role,
                "connected_at": conn.connected_at.isoformat(),
            })
        )
        return conn

    async def disconnect_frontend(self, conn: FrontendConnection) -> None:
        if isinstance(self._frontends, list) and conn in self._frontends:
            self._frontends.remove(conn)
        logger.info("Frontend user %s disconnected.", conn.user_id)
        # Broadcast operator disconnect
        await self.broadcast_to_frontends(
            build_message("operator_disconnected", {
                "user_id": conn.user_id,
                "username": conn.username,
            })
        )

    def get_online_operators(self) -> list[dict]:
        """Return list of currently connected operators with presence info."""
        if not isinstance(self._frontends, list):
            return []
        return [
            {
                "user_id": conn.user_id,
                "username": conn.username,
                "role": conn.role,
                "connected_at": conn.connected_at.isoformat(),
                "last_activity": conn.last_activity.isoformat(),
                "current_page": conn.current_page,
            }
            for conn in self._frontends if conn._alive
        ]

    async def update_operator_presence(self, user_id: str, page: str = "", cursor: str = "") -> None:
        """Update an operator's presence info (current page, cursor)."""
        if not isinstance(self._frontends, list):
            return
        for conn in self._frontends:
            if conn.user_id == user_id and conn._alive:
                conn.last_activity = datetime.now(timezone.utc)
                if page:
                    conn.current_page = page
                if cursor:
                    conn.cursor_position = cursor
                break

    # --- Sending ---

    async def send_to_agent(self, agent_id: str, message: dict) -> bool:
        conn = self._agents.get(agent_id)
        if conn:
            return await conn.send(message)
        logger.debug("Agent %s not connected — queuing message.", agent_id)
        _orphan = AgentConnection.__new__(AgentConnection)
        _orphan.agent_id = agent_id
        _orphan._offline_queue = []
        _orphan._alive = False
        _orphan._enqueue_offline(message)
        return False

    async def broadcast_to_group(self, agent_ids: list[str], message: dict) -> None:
        coros = [self.send_to_agent(aid, message) for aid in agent_ids]
        await asyncio.gather(*coros, return_exceptions=True)

    async def broadcast_to_channel(self, channel: str, message: dict) -> None:
        """Send to all agents subscribed to a channel."""
        targets = [
            conn for conn in self._agents.values() if conn.is_subscribed(channel)
        ]
        await asyncio.gather(*[c.send(message) for c in targets], return_exceptions=True)

    async def broadcast_to_frontends(self, message: dict, channel: str = "*") -> None:
        if not isinstance(self._frontends, list):
            return
        dead = []
        for conn in self._frontends:
            if conn.is_subscribed(channel):
                ok = await conn.send(message)
                if not ok:
                    dead.append(conn)
        for conn in dead:
            try:
                self._frontends.remove(conn)
            except ValueError:
                pass

    # --- Router ---

    @property
    def router(self) -> MessageRouter:
        return self._router

    def register_handler(self, msg_type: str, handler: MessageHandler) -> None:
        self._router.register(msg_type, handler)

    async def route_agent_message(self, agent_id: str, message: dict) -> None:
        conn = self._agents.get(agent_id)
        if conn:
            conn.touch()
        await self._router.route(agent_id, message)

    # --- Queries ---

    def get_connected_agent_ids(self) -> list[str]:
        return [aid for aid, conn in self._agents.items() if conn._alive]

    def get_agent_connection(self, agent_id: str) -> Optional[AgentConnection]:
        return self._agents.get(agent_id)

    def agent_is_online(self, agent_id: str) -> bool:
        conn = self._agents.get(agent_id)
        return conn is not None and conn._alive

    def stats(self) -> dict:
        return {
            "agents_connected": len([c for c in self._agents.values() if c._alive]),
            "agents_total": len(self._agents),
            "frontends_connected": len(self._frontends) if isinstance(self._frontends, list) else 0,
        }

    # --- DB sync ---

    @staticmethod
    async def _sync_agent_status(agent_id: str, status: str) -> None:
        try:
            from database import database
            from db.models import Agent

            with database:
                Agent.update(
                    status=status,
                    last_seen=datetime.now(timezone.utc),
                ).where(Agent.id == agent_id).execute()
        except Exception as exc:
            logger.debug("Agent status sync failed for %s: %s", agent_id, exc)
