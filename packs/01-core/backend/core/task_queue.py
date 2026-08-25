"""
Task queue manager — dispatches tasks to agents via WS or queues them in Celery.
Supports 4 priority levels: critical, high, normal, low.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import os

from database import database
from db.models import Task

logger = logging.getLogger(__name__)

PORTABLE_MODE = os.getenv("PORTABLE_MODE", "false").lower() in ("1", "true", "yes")

PRIORITY_MAP = {"critical": 9, "high": 6, "normal": 3, "low": 1}
QUEUE_MAP = {"critical": "critical", "high": "high", "normal": "normal", "low": "low"}

celery_app = None
try:
    from core.celery_app import celery_app as _celery_app

    celery_app = _celery_app
except Exception as exc:
    logger.warning("Celery not available; task queue will use direct dispatch only. %s", exc)


class TaskQueue:
    _instance: Optional["TaskQueue"] = None

    def __new__(cls) -> "TaskQueue":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def enqueue(
        self,
        agent_id: str,
        module: str,
        action: str = "run",
        params: dict | None = None,
        priority: str = "normal",
        timeout: int = 60,
        timeline_id: str | None = None,
        retries: int = 3,
    ) -> Task:
        """Create a task record and dispatch it to the agent or Celery queue."""
        params = params or {}

        with database:
            task = Task.create(
                agent=agent_id,
                module=module,
                action=action,
                params=json.dumps(params),
                priority=priority,
                timeout=timeout,
                status="queued",
                timeline_id=timeline_id or "",
            )

        dispatched = await self._dispatch_ws(task, agent_id)
        if not dispatched:
            if celery_app is not None:
                self._dispatch_celery(str(task.id), agent_id, module, action, params, priority, timeout, retries)
            else:
                logger.info(
                    "Task %s queued locally (agent offline, Celery unavailable in portable mode).",
                    task.id,
                )

        return task

    async def _dispatch_ws(self, task: Task, agent_id: str) -> bool:
        """Try to deliver directly via WebSocket. Returns True if sent."""
        try:
            from core.ws_manager import ConnectionManager, build_message
            from core.result_buffer import ResultBuffer
            manager = ConnectionManager()
            conn = manager.get_agent_connection(agent_id)
            if conn:
                task_id = str(task.id)
                ResultBuffer().register_module(task_id, task.module)
                msg = build_message("task", {
                    "task_id": task_id,
                    "module": task.module,
                    "action": task.action,
                    "params": json.loads(task.params),
                    "timeout": task.timeout,
                }, agent_id=agent_id)
                await conn.send(msg)
                with database:
                    Task.update(status="running", executed_at=datetime.now(timezone.utc)).where(Task.id == task.id).execute()
                return True
        except Exception as exc:
            logger.debug("WS dispatch failed for task %s: %s", task.id, exc)
        return False

    def _dispatch_celery(
        self, task_id: str, agent_id: str, module: str, action: str,
        params: dict, priority: str, timeout: int, retries: int,
    ) -> None:
        """Push task to the Celery queue for deferred delivery."""
        queue = QUEUE_MAP.get(priority, "normal")
        celery_priority = PRIORITY_MAP.get(priority, 3)

        dispatch_task.apply_async(
            args=[task_id, agent_id, module, action, params, timeout],
            queue=queue,
            priority=celery_priority,
            countdown=0,
            retry=retries > 0,
            retry_policy={"max_retries": retries, "interval_start": 2, "interval_step": 5, "interval_max": 30},
        )
        logger.info("Task %s queued via Celery (queue=%s, priority=%s)", task_id, queue, priority)

    async def cancel(self, task_id: str) -> bool:
        task = Task.get_or_none(Task.id == task_id)
        if not task or task.status in ("completed", "failed", "cancelled"):
            return False
        if celery_app is not None:
            try:
                celery_app.control.revoke(task_id, terminate=True)
            except Exception as exc:
                logger.debug("Celery revoke failed for task %s: %s", task_id, exc)
        with database:
            Task.update(status="cancelled").where(Task.id == task_id).execute()
        return True

    def list_tasks(
        self,
        agent_id: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        q = Task.select().order_by(Task.created_at.desc())
        if agent_id:
            q = q.where(Task.agent == agent_id)
        if status:
            q = q.where(Task.status == status)
        if priority:
            q = q.where(Task.priority == priority)
        return list(q.offset(offset).limit(limit))


@celery_app.task(bind=True, name="tasks.normal.dispatch_task", max_retries=3)
def dispatch_task(self, task_id: str, agent_id: str, module: str, action: str, params: dict, timeout: int):
    """Celery task to deliver a deferred task to a connected agent."""
    import asyncio
    from core.ws_manager import ConnectionManager, build_message

    manager = ConnectionManager()
    conn = manager.get_agent_connection(agent_id)
    if not conn:
        logger.warning("Agent %s still offline for task %s, retrying…", agent_id, task_id)
        raise self.retry(countdown=30)

    msg = build_message("task", {
        "task_id": task_id, "module": module, "action": action,
        "params": params, "timeout": timeout,
    }, agent_id=agent_id)

    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(conn.send(msg))
        loop.close()
        with database:
            Task.update(status="running", executed_at=datetime.now(timezone.utc)).where(Task.id == task_id).execute()
    except Exception as exc:
        logger.error("Celery dispatch failed for task %s: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=10)
