#!/usr/bin/env python
"""
Celery worker entry point.

Usage:
  # Analysis + default queues
  celery -A celery_worker.celery_app worker --loglevel=info -Q analysis,default -c 4

  # Export queue (separate process)
  celery -A celery_worker.celery_app worker --loglevel=info -Q export -c 2

  # All queues
  celery -A celery_worker.celery_app worker --loglevel=info -Q analysis,export,default -c 4

  # Flower monitoring
  celery -A celery_worker.celery_app flower --port=5555
"""
import os
from pathlib import Path

# Add venv/Scripts to PATH for subprocesses (ffmpeg, ffprobe, etc.)
venv_scripts = str(Path(__file__).parent / "venv" / "Scripts")
if venv_scripts not in os.environ["PATH"]:
    os.environ["PATH"] = venv_scripts + os.pathsep + os.environ["PATH"]

from app.workers.celery_app import celery_app  # noqa: F401 — Celery discovers tasks via include

if __name__ == "__main__":
    celery_app.start()
