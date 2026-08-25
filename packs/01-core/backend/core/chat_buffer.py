"""
Chat buffer — amortises persisted chat event writes.

Chat event persistence is moved off the hot WebSocket path into a short-lived
in-memory buffer flushed every 2 seconds. Frontend still receives immediate
WS broadcasts; only the DB write is deferred.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from database import database
from db.models import ChatMessage

logger = logging.getLogger(__name__)

DEFAULT_FLUSH_INTERVAL = 2.0


class ChatBuffer:
    """Singleton buffered writer for chat/event messages."""

    _instance: Optional["ChatBuffer"] = None

    def __new__(cls) -> "ChatBuffer":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._buffer: list[dict[str, Any]] = []
            inst._task: Optional[asyncio.Task] = None
            inst._loop: Optional[asyncio.AbstractEventLoop] = None
            inst._interval = DEFAULT_FLUSH_INTERVAL
            inst._running = False
            cls._instance = inst
        return cls._instance

    def push(self, event_type: str, payload: dict, channel: str = "global") -> None:
        """Queue a chat message for batched persistence."""
        from core.chat_engine import engine as chat_engine
        try:
            chat_msg = chat_engine.render_event(event_type, payload)
            self._buffer.append({
                "role": "event",
                "content": chat_msg["content"],
                "source_event_type": event_type,
                "channel": channel,
                "raw_payload": json.dumps(payload),
                "metadata": json.dumps(chat_msg.get("metadata", {})),
                "agent_id": payload.get("agent_id"),
                "task_id": payload.get("task_id"),
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as exc:
            logger.debug("Chat render failed: %s", exc)

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
        logger.debug("Chat buffer started (interval=%.1fs).", interval)

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
                logger.exception("Chat flush loop error")

    async def _flush(self) -> None:
        batch = self._buffer
        self._buffer = []
        if not batch:
            return

        def _bulk_write() -> None:
            with database.atomic():
                ChatMessage.insert_many(batch).execute()

        try:
            await asyncio.to_thread(_bulk_write)
            logger.debug("Flushed %d chat messages to DB.", len(batch))
        except Exception:
            logger.exception("Chat bulk flush failed")
