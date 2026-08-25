"""
Result buffer — amortise high-frequency task result writes.

Task result updates are merged in memory and flushed to SQLite on a short
cadence (default 2 s). This avoids N individual UPDATE/SELECT round-trips
when a flood of results arrives from many agents.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from database import database
from db.models import Task

logger = logging.getLogger(__name__)

DEFAULT_FLUSH_INTERVAL = 2.0


class ResultBuffer:
    """Singleton buffered updater for task results."""

    _instance: Optional["ResultBuffer"] = None

    def __new__(cls) -> "ResultBuffer":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._buffer: dict[str, dict[str, Any]] = {}
            inst._module_cache: dict[str, str] = {}
            inst._task: Optional[asyncio.Task] = None
            inst._loop: Optional[asyncio.AbstractEventLoop] = None
            inst._interval = DEFAULT_FLUSH_INTERVAL
            inst._running = False
            cls._instance = inst
        return cls._instance

    def register_module(self, task_id: str, module: str) -> None:
        """Cache the module name for a task when it is dispatched."""
        self._module_cache[task_id] = module

    def get_module(self, task_id: str) -> str | None:
        return self._module_cache.get(task_id)

    def push(self, task_id: str, status: str, result: dict | None, error: str | None) -> None:
        """Merge a result update into the pending buffer."""
        merged = self._buffer.get(task_id, {})
        merged.update({
            "status": status,
            "result": json.dumps(result) if result is not None else None,
            "error": error,
            "executed_at": datetime.now(timezone.utc),
        })
        self._buffer[task_id] = merged

    def get_status(self, task_id: str) -> str | None:
        """Return the buffered status for a task without hitting the DB."""
        return self._buffer.get(task_id, {}).get("status")

    async def start(self, interval: float = DEFAULT_FLUSH_INTERVAL) -> None:
        current_loop = asyncio.get_running_loop()
        if self._running and self._loop is current_loop and self._task and not self._task.done():
            return
        if self._task and self._loop is not current_loop:
            self._task.cancel()
        self._interval = interval
        self._running = True
        self._loop = current_loop
        self._task = asyncio.create_task(self._flush_loop())
        logger.debug("Result buffer started (interval=%.1fs).", interval)

    async def stop(self) -> None:
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
                logger.exception("Result flush loop error")

    async def _flush(self) -> None:
        snapshot = self._buffer
        self._buffer = {}
        if not snapshot:
            return

        def _bulk_write() -> None:
            now = datetime.now(timezone.utc)
            with database.atomic():
                for task_id, payload in snapshot.items():
                    updates = {
                        "status": payload["status"],
                        "executed_at": payload.get("executed_at") or now,
                    }
                    if payload.get("result") is not None:
                        updates["result"] = payload["result"]
                    if payload.get("error") is not None:
                        updates["error"] = payload["error"]
                    Task.update(**updates).where(Task.id == task_id).execute()

        try:
            await asyncio.to_thread(_bulk_write)
            logger.debug("Flushed %d task results to DB.", len(snapshot))
        except Exception:
            logger.exception("Result bulk flush failed")
