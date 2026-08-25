"""
Prometheus metrics integration for Lucy.

Exposes:
- http_requests_total          : counter by method, path, status
- http_request_duration_seconds: histogram by method, path
- lucy_agents_total            : gauge of agents by status
- lucy_tasks_total             : gauge of tasks by status
- lucy_library_resources_total : gauge of resources by type
"""
from __future__ import annotations

import time
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Isolated registry so we can expose only Lucy metrics
REGISTRY = CollectorRegistry()

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    registry=REGISTRY,
)

lucy_agents_total = Gauge(
    "lucy_agents_total",
    "Number of agents by status",
    ["status"],
    registry=REGISTRY,
)

lucy_tasks_total = Gauge(
    "lucy_tasks_total",
    "Number of tasks by status",
    ["status"],
    registry=REGISTRY,
)

lucy_library_resources_total = Gauge(
    "lucy_library_resources_total",
    "Number of library resources by type",
    ["resource_type"],
    registry=REGISTRY,
)


def observe_request(method: str, path: str, status: int, duration: float) -> None:
    """Record an HTTP request in the request counter and latency histogram."""
    http_requests_total.labels(method=method, path=path, status=str(status)).inc()
    http_request_duration_seconds.labels(method=method, path=path).observe(duration)


def refresh_gauges() -> None:
    """Refresh entity gauges from the database."""
    try:
        from db.models import Agent, Resource, Task

        for status in ["online", "offline", "idle", "unknown"]:
            count = Agent.select().where(Agent.status == status).count()
            lucy_agents_total.labels(status=status).set(count)

        for status in ["queued", "running", "completed", "failed", "cancelled"]:
            count = Task.select().where(Task.status == status).count()
            lucy_tasks_total.labels(status=status).set(count)

        q = Resource.select(Resource.resource_type).distinct()
        for row in q:
            count = Resource.select().where(Resource.resource_type == row.resource_type).count()
            lucy_library_resources_total.labels(resource_type=row.resource_type).set(count)
    except Exception:
        # Gauges are best-effort; never break the application.
        pass


def get_metrics() -> bytes:
    """Return Prometheus exposition format."""
    refresh_gauges()
    return generate_latest(REGISTRY)
