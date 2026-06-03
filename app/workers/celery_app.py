"""
Celery application factory.
Import this in both the FastAPI app and the worker process.
"""
from __future__ import annotations

from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "videoedit",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.analysis_tasks",
        "app.workers.export_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,       # one task at a time per worker
    task_soft_time_limit=3300,          # 55-min soft limit
    task_time_limit=3600,               # 60-min hard limit
    result_expires=86400,               # keep results 24h
    worker_max_tasks_per_child=50,      # restart worker after 50 tasks (memory safety)
    broker_connection_retry_on_startup=True,
)

# ── Optional: routing — heavy analysis on 'analysis' queue ────────────────────
celery_app.conf.task_routes = {
    "app.workers.analysis_tasks.*": {"queue": "analysis"},
    "app.workers.export_tasks.*": {"queue": "export"},
}

celery_app.conf.task_default_queue = "default"
