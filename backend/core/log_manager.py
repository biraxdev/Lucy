import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

_LOG_TYPES = {"system", "agent", "task", "module", "security"}


class LogManager:
    """Singleton centralized log manager with async buffered writes."""

    _instance: Optional["LogManager"] = None
    _buffer: list[dict]
    _flush_interval: float = 5.0
    _flush_threshold: int = 100
    _task: Optional[asyncio.Task] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None

    def __new__(cls) -> "LogManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._buffer = []
        return cls._instance

    async def start(self) -> None:
        current_loop = asyncio.get_running_loop()
        if self._task and self._loop is current_loop and not self._task.done():
            return
        if self._task and self._loop is not current_loop:
            self._task.cancel()
        self._loop = current_loop
        self._task = asyncio.create_task(self._flush_loop())
        logger.info("LogManager started.")

    async def stop(self) -> None:
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
        if self._loop is current_loop:
            await self._flush()
        logger.info("LogManager stopped.")

    def push(
        self,
        level: str,
        message: str,
        module: str = "system",
        agent_id: Optional[str] = None,
        log_type: str = "system",
    ) -> None:
        entry = {
            "id": str(uuid4()),
            "agent_id": agent_id,
            "level": level.upper(),
            "module": module,
            "message": message,
            "log_type": log_type if log_type in _LOG_TYPES else "system",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._buffer.append(entry)
        if len(self._buffer) >= self._flush_threshold:
            asyncio.create_task(self._flush())

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            await self._flush()

    async def _flush(self) -> None:
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            from db.models import Log

            with Log._meta.database:
                Log.insert_many(batch).execute()
        except Exception as exc:
            logger.error("LogManager flush failed: %s", exc)
            self._buffer.extend(batch)
