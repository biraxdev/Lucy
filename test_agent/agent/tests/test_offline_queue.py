"""
Tests for the agent offline queue.

Run from the project root:
    cd agent
    python -m pytest tests/test_offline_queue.py -v
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.offline_queue import OfflineQueue


class TestOfflineQueue:
    def test_enqueue_and_dequeue_result(self):
        q = OfflineQueue()
        q.enqueue_result({"task_id": "1", "status": "completed"})
        assert q.result_count() == 1
        item = q.dequeue_result()
        assert item["task_id"] == "1"
        assert q.result_count() == 0

    def test_enqueue_and_dequeue_task(self):
        q = OfflineQueue()
        q.enqueue_task({"module": "shell", "action": "whoami"})
        assert q.task_count() == 1
        item = q.dequeue_task()
        assert item["module"] == "shell"
        assert q.task_count() == 0

    def test_max_results_limit(self):
        q = OfflineQueue(max_results=3, max_tasks=3)
        for i in range(5):
            q.enqueue_result({"task_id": str(i)})
        assert q.result_count() == 3
        assert q.dequeue_result()["task_id"] == "2"

    def test_max_tasks_limit(self):
        q = OfflineQueue(max_results=3, max_tasks=3)
        for i in range(5):
            q.enqueue_task({"task_id": str(i)})
        assert q.task_count() == 3
        assert q.dequeue_task()["task_id"] == "2"

    def test_flush_results_success(self):
        q = OfflineQueue()
        q.enqueue_result({"task_id": "1"})
        q.enqueue_result({"task_id": "2"})

        sent = []
        def send_fn(result):
            sent.append(result)

        count = q.flush_results(send_fn)
        assert count == 2
        assert q.result_count() == 0
        assert [r["task_id"] for r in sent] == ["1", "2"]

    def test_flush_results_requeue_on_failure(self):
        q = OfflineQueue()
        q.enqueue_result({"task_id": "1"})
        q.enqueue_result({"task_id": "2"})

        calls = []
        def send_fn(result):
            calls.append(result)
            if len(calls) == 1:
                raise RuntimeError("boom")

        count = q.flush_results(send_fn)
        assert count == 0
        assert q.result_count() == 2
        # failed item is put back at the tail, so order is preserved
        assert q.dequeue_result()["task_id"] == "1"
        assert q.dequeue_result()["task_id"] == "2"

    def test_peek_does_not_remove(self):
        q = OfflineQueue()
        q.enqueue_result({"task_id": "1"})
        assert len(q.peek_results()) == 1
        assert q.result_count() == 1

    def test_clear(self):
        q = OfflineQueue()
        q.enqueue_result({"task_id": "1"})
        q.enqueue_task({"task_id": "2"})
        q.clear()
        assert q.result_count() == 0
        assert q.task_count() == 0
