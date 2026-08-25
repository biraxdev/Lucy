"""
Heartbeat buffer — amortise high-frequency agent heartbeats.

Instead of updating the SQLite `agents` table on every heartbeat, incoming
heartbeats are merged into an in-memory map and flushed to the database on a
fixed cadence (default 5s). This removes the write bottleneck when many agents
are online and keeps `last_seen` reasonably fresh.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from database import database
from db.models import Agent

logger = logging.getLogger(__name__)

DEFAULT_FLUSH_INTERVAL = 5.0


class HeartbeatBuffer:
    """Singleton in-memory buffer for agent heartbeat metadata."""

    _instance: Optional["HeartbeatBuffer"] = None

    def __new__(cls) -> "HeartbeatBuffer":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._buffer: dict[str, dict] = {}
            inst._task: Optional[asyncio.Task] = None
            inst._loop: Optional[asyncio.AbstractEventLoop] = None
            inst._interval = DEFAULT_FLUSH_INTERVAL
            inst._running = False
            cls._instance = inst
        return cls._instance

    def push(self, agent_id: str, payload: dict) -> None:
        """Merge a heartbeat payload into the pending buffer."""
        merged = self._buffer.get(agent_id, {})
        merged.update(payload)
        merged["agent_id"] = agent_id
        self._buffer[agent_id] = merged

    async def start(self, interval: float = DEFAULT_FLUSH_INTERVAL) -> None:
        """Start the periodic flush loop."""
        current_loop = asyncio.get_running_loop()
        if self._running and self._loop is current_loop and self._task and not self._task.done():
            return
        if self._task and self._loop is not current_loop:
            self._task.cancel()
        self._interval = interval
        self._running = True
        self._loop = current_loop
        self._task = asyncio.create_task(self._flush_loop())
        logger.debug("Heartbeat buffer started (interval=%.1fs).", interval)

    async def stop(self) -> None:
        """Stop the loop and flush remaining items immediately."""
        self._running = False
        current_loop = asyncio.get_running_loop()
        if self._task:
            if self._loop is current_loop:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            else:
                self._task.cancel()
            self._task = None
        if self._buffer and self._loop is current_loop:
            await self._flush()

    async def _flush_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if self._buffer:
                    await self._flush()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat flush loop error")

    async def _flush(self) -> None:
        """Persist all buffered heartbeats in a single transaction."""
        snapshot = self._buffer
        self._buffer = {}

        now = datetime.now(timezone.utc)
        updates = []
        for agent_id, payload in snapshot.items():
            update = {
                "status": "online",
                "last_seen": now,
            }
            if payload.get("ram_available") is not None:
                update["ram_available"] = payload["ram_available"]
            if payload.get("cpu_percent") is not None:
                update["cpu_percent"] = payload["cpu_percent"]
            updates.append((agent_id, update))

        if not updates:
            return

        def _bulk_write() -> None:
            with database.atomic():
                for agent_id, update in updates:
                    Agent.update(**update).where(Agent.id == agent_id).execute()

        try:
            await asyncio.to_thread(_bulk_write)
            logger.debug("Flushed %d heartbeats to DB.", len(updates))
        except Exception:
            logger.exception("Heartbeat bulk flush failed")
