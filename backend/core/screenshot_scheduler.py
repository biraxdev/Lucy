"""
Screenshot Scheduler — automatically dispatches screenshot tasks to online
agents at a configurable interval.

The scheduler runs as a background asyncio task.  It creates screenshot tasks
for all online agents (or a specific subset) every N minutes and records the
last-captured timestamp per agent so the UI can display freshness.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from database import database
from db.models import Agent, Task

logger = logging.getLogger(__name__)


class ScreenshotScheduler:
    """Singleton scheduler that auto-captures screenshots from agents."""

    _instance: Optional["ScreenshotScheduler"] = None

    def __new__(cls) -> "ScreenshotScheduler":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._task: Optional[asyncio.Task] = None
            inst._loop: Optional[asyncio.AbstractEventLoop] = None
            inst._running = False
            inst._interval_minutes = 5
            inst._quality = 70
            inst._max_width = 1280
            inst._target_mode = "online"  # online | all | specific
            inst._target_agent_ids: list[str] = []
            inst._last_capture: dict[str, str] = {}  # agent_id -> ISO timestamp
            inst._capture_count = 0
            cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    def get_config(self) -> dict:
        return {
            "running": self._running,
            "interval_minutes": self._interval_minutes,
            "quality": self._quality,
            "max_width": self._max_width,
            "target_mode": self._target_mode,
            "target_agent_ids": self._target_agent_ids,
            "capture_count": self._capture_count,
            "last_capture": dict(self._last_capture),
        }

    def configure(
        self,
        interval_minutes: int | None = None,
        quality: int | None = None,
        max_width: int | None = None,
        target_mode: str | None = None,
        target_agent_ids: list[str] | None = None,
    ) -> dict:
        if interval_minutes is not None:
            self._interval_minutes = max(1, min(1440, int(interval_minutes)))
        if quality is not None:
            self._quality = max(10, min(100, int(quality)))
        if max_width is not None:
            self._max_width = max(320, min(3840, int(max_width)))
        if target_mode is not None:
            self._target_mode = target_mode if target_mode in ("online", "all", "specific") else "online"
        if target_agent_ids is not None:
            self._target_agent_ids = target_agent_ids
        return self.get_config()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> dict:
        current_loop = asyncio.get_running_loop()
        if self._running and self._loop is current_loop and self._task and not self._task.done():
            return self.get_config()
        self._loop = current_loop
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("ScreenshotScheduler started (interval=%dm).", self._interval_minutes)
        return self.get_config()

    async def stop(self) -> dict:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ScreenshotScheduler stopped.")
        return self.get_config()

    async def trigger_now(self) -> dict:
        """Capture immediately without waiting for the next interval."""
        dispatched = await self._dispatch_screenshots()
        return {"dispatched": dispatched, "last_capture": dict(self._last_capture)}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        # Capture immediately on start, then wait for the interval.
        while self._running:
            try:
                await self._dispatch_screenshots()
                await asyncio.sleep(self._interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("ScreenshotScheduler loop error")
                await asyncio.sleep(60)  # back off on error

    async def _dispatch_screenshots(self) -> int:
        agent_ids = self._resolve_targets()
        if not agent_ids:
            return 0

        now_iso = datetime.now(timezone.utc).isoformat()
        params = {
            "mode": "single",
            "quality": self._quality,
            "max_width": self._max_width,
            "format": "jpeg",
        }
        params_json = json.dumps(params)
        dispatched = 0

        def _create_tasks() -> int:
            count = 0
            with database.atomic():
                for aid in agent_ids:
                    Task.create(
                        agent=aid,
                        module="screenshot",
                        action="capture",
                        params=params_json,
                        status="queued",
                        priority="low",
                    )
                    count += 1
            return count

        try:
            dispatched = await asyncio.to_thread(_create_tasks)
            for aid in agent_ids:
                self._last_capture[aid] = now_iso
            self._capture_count += dispatched
            logger.info("ScreenshotScheduler: dispatched %d screenshot tasks.", dispatched)
        except Exception:
            logger.exception("ScreenshotScheduler: failed to dispatch tasks.")

        return dispatched

    def _resolve_targets(self) -> list[str]:
        if self._target_mode == "specific":
            # Only keep IDs that still exist
            valid = set(str(a.id) for a in Agent.select(Agent.id).where(Agent.id.in_(self._target_agent_ids)))
            return [aid for aid in self._target_agent_ids if aid in valid]
        elif self._target_mode == "all":
            return [str(a.id) for a in Agent.select(Agent.id)]
        else:  # online
            return [str(a.id) for a in Agent.select(Agent.id).where(Agent.status == "online")]
