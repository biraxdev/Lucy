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
RETRY_DELAYS = [10, 30, 60]  # seconds between retries

celery_app = None
_redis_available = False
try:
    from core.celery_app import celery_app as _celery_app

    celery_app = _celery_app
    # Check if Redis is actually reachable (non-blocking, short timeout)
    import socket
    _redis_host = "localhost"
    _redis_port = 6379
    try:
        _sock = socket.create_connection((_redis_host, _redis_port), timeout=1)
        _sock.close()
        _redis_available = True
    except (OSError, ConnectionRefusedError):
        logger.warning("Redis not reachable at %s:%s — task queue will use in-memory worker.", _redis_host, _redis_port)
except Exception as exc:
    logger.warning("Celery not available; task queue will use in-memory worker. %s", exc)


# ─── In-memory task worker (portable mode, no Redis) ────────────────────────
import threading
import queue
import time


class _InMemoryWorker:
    """Thread-based task queue that runs when Celery is unavailable."""

    def __init__(self) -> None:
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._worker: threading.Thread | None = None
        self._shutdown = threading.Event()
        self._running = set()  # task_ids currently being processed

    def start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._shutdown.clear()
        self._worker = threading.Thread(target=self._run, daemon=True, name="LucyTaskWorker")
        self._worker.start()
        logger.info("In-memory task worker started (portable mode).")

    def stop(self) -> None:
        self._shutdown.set()
        if self._worker:
            self._worker.join(timeout=5)

    def enqueue(
        self,
        task_id: str,
        agent_id: str,
        module: str,
        action: str,
        params: dict,
        priority: str,
        timeout: int,
        retries: int = 3,
    ) -> None:
        prio = -PRIORITY_MAP.get(priority, 3)  # negative for highest-first
        self._queue.put((prio, time.time(), task_id, agent_id, module, action, params, timeout, retries, 0))
        logger.info("Task %s queued in-memory (priority=%s, retries=%d)", task_id, priority, retries)

    def _run(self) -> None:
        while not self._shutdown.is_set():
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            _, _, task_id, agent_id, module, action, params, timeout, retries, attempt = item

            if task_id in self._running:
                # Re-queue if already running (shouldn't happen often)
                self._queue.put(item)
                continue

            self._running.add(task_id)
            try:
                success = self._try_dispatch(task_id, agent_id, module, action, params, timeout)
                if success:
                    continue

                if attempt < retries:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    logger.info("Task %s retry %d/%d in %ds", task_id, attempt + 1, retries, delay)
                    time.sleep(delay)
                    self._queue.put((item[0], time.time(), task_id, agent_id, module, action, params, timeout, retries, attempt + 1))
                else:
                    logger.warning("Task %s exhausted all retries (%d).", task_id, retries)
                    with database:
                        Task.update(status="failed").where(Task.id == task_id).execute()
            finally:
                self._running.discard(task_id)

    def _try_dispatch(self, task_id: str, agent_id: str, module: str, action: str, params: dict, timeout: int) -> bool:
        """Attempt to dispatch via WebSocket. Returns True if sent."""
        try:
            from core.ws_manager import ConnectionManager, build_message
            from core.result_buffer import ResultBuffer

            manager = ConnectionManager()
            conn = manager.get_agent_connection(agent_id)
            if not conn:
                logger.debug("In-memory dispatch: agent %s not connected", agent_id)
                return False

            ResultBuffer().register_module(task_id, module)
            msg = build_message("task", {
                "task_id": task_id,
                "module": module,
                "action": action,
                "params": params,
                "timeout": timeout,
            }, agent_id=agent_id)

            # WS send is async — run in a new event loop from this thread
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(conn.send(msg))
            finally:
                loop.close()

            with database:
                Task.update(status="running", executed_at=datetime.now(timezone.utc)).where(Task.id == task_id).execute()
            logger.info("Task %s dispatched via in-memory worker.", task_id)
            return True
        except Exception as exc:
            logger.warning("In-memory dispatch failed for task %s: %s", task_id, exc)
            return False


in_memory_worker = _InMemoryWorker()


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
            if celery_app is not None and _redis_available:
                self._dispatch_celery(str(task.id), agent_id, module, action, params, priority, timeout, retries)
            else:
                in_memory_worker.enqueue(
                    task_id=str(task.id),
                    agent_id=agent_id,
                    module=module,
                    action=action,
                    params=params,
                    priority=priority,
                    timeout=timeout,
                    retries=retries,
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
                logger.info("Task %s dispatched via WS to agent %s", task_id, agent_id)
                return True
            else:
                logger.info("WS dispatch: agent %s not connected (no WS connection), queuing", agent_id)
        except Exception as exc:
            logger.warning("WS dispatch failed for task %s: %s", task.id, exc)
        return False

    def _dispatch_celery(
        self, task_id: str, agent_id: str, module: str, action: str,
        params: dict, priority: str, timeout: int, retries: int,
    ) -> None:
        """Push task to the Celery queue for deferred delivery."""
        queue = QUEUE_MAP.get(priority, "normal")
        celery_priority = PRIORITY_MAP.get(priority, 3)

        try:
            dispatch_task.apply_async(
                args=[task_id, agent_id, module, action, params, timeout],
                queue=queue,
                priority=celery_priority,
                countdown=0,
                retry=False,
            )
            logger.info("Task %s queued via Celery (queue=%s, priority=%s)", task_id, queue, priority)
        except Exception as exc:
            logger.warning("Celery dispatch failed for task %s: %s — task remains queued in DB for heartbeat pickup", task_id, exc)

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
