"""
Celery application factory for Project Lucy.
"""
import os
from celery import Celery

BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BACKEND_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "lucy",
    broker=BROKER_URL,
    backend=BACKEND_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "tasks.critical.*": {"queue": "critical"},
        "tasks.high.*": {"queue": "high"},
        "tasks.normal.*": {"queue": "normal"},
        "tasks.low.*": {"queue": "low"},
    },
    task_default_queue="normal",
    task_queues={
        "critical": {"exchange": "critical", "routing_key": "critical"},
        "high": {"exchange": "high", "routing_key": "high"},
        "normal": {"exchange": "normal", "routing_key": "normal"},
        "low": {"exchange": "low", "routing_key": "low"},
    },
    result_expires=3600,
    worker_max_tasks_per_child=500,
)

celery_app.autodiscover_tasks(["core.task_queue"])
