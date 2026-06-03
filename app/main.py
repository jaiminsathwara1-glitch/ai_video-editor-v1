"""
FastAPI application entry point.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add venv/Scripts to PATH for subprocesses (ffmpeg, ffprobe, etc.)
venv_scripts = str(Path(__file__).parent.parent / "venv" / "Scripts")
if venv_scripts not in os.environ["PATH"]:
    os.environ["PATH"] = venv_scripts + os.pathsep + os.environ["PATH"]

import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db
from app.routes import projects, clips, analysis, timelines

log = structlog.get_logger(__name__)
settings = get_settings()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("startup", env=settings.app_env)
    await init_db()
    yield
    log.info("shutdown")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Video Rough-Cut Platform",
        description=(
            "Production-ready backend for AI-assisted video editing. "
            "Upload 4K clips → analyse → generate rough-cut timeline → export to Premiere XML."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": type(exc).__name__},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(clips.router, prefix="/api/v1")
    app.include_router(analysis.router, prefix="/api/v1")
    app.include_router(timelines.router, prefix="/api/v1")

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health() -> dict:
        return {"status": "ok", "version": app.version, "env": settings.app_env}

    @app.get("/health/workers", tags=["Health"])
    async def health_workers() -> dict:
        """
        Check if Celery workers are online and which queues they serve.
        Returns worker_online=False when analysis worker has crashed.
        """
        try:
            from app.workers.celery_app import celery_app as _celery
            inspector = _celery.control.inspect(timeout=3.0)
            active_queues = inspector.active_queues() or {}

            workers = []
            analysis_online = False
            export_online = False

            for worker_name, queues in active_queues.items():
                queue_names = [q["name"] for q in queues]
                workers.append({"name": worker_name, "queues": queue_names})
                if "analysis" in queue_names or "default" in queue_names:
                    analysis_online = True
                if "export" in queue_names:
                    export_online = True

            return {
                "status": "ok" if analysis_online else "degraded",
                "analysis_worker_online": analysis_online,
                "export_worker_online": export_online,
                "workers": workers,
                "warning": None if analysis_online else (
                    "Analysis worker is OFFLINE. Run: "
                    "celery -A celery_worker.celery_app worker --loglevel=info -Q analysis,default -P threads -c 4"
                ),
            }
        except Exception as exc:
            return {
                "status": "error",
                "analysis_worker_online": False,
                "export_worker_online": False,
                "workers": [],
                "warning": f"Could not contact Celery: {exc}",
            }

    @app.get("/", tags=["Health"])
    async def root() -> dict:
        return {
            "message": "AI Video Rough-Cut Platform API",
            "docs": "/docs",
            "health": "/health",
            "workers": "/health/workers",
        }

    return app


app = create_app()
