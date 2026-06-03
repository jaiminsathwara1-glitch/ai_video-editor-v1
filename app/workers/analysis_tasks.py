"""
Celery analysis tasks.

Each task:
  1. Runs CV analysis (blur, shake, exposure, scenes)
  2. Runs Whisper transcription
  3. Runs LLM tagger (structured metadata only)
  4. Persists results to SQLite via a synchronous SQLAlchemy session
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import structlog
from celery import states
from celery.exceptions import Ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings
from app.workers.celery_app import celery_app
from app.ai.cv_analyser import analyse_clip_cv, find_duplicates
from app.ai.scene_detector import detect_scenes
from app.ai.transcriber import transcribe_clip
from app.ai.llm_scorer import tag_and_summarise

# ── Import ALL models at module level so SQLAlchemy mapper resolves all
# relationships (e.g. Clip.analysis → ClipAnalysis) before any task runs.
# Without this, the first db.query(Clip) raises InvalidRequestError.
from app.models.clip import Clip, ClipChunk          # noqa: F401
from app.models.project import Project                # noqa: F401
from app.models.analysis import ClipAnalysis          # noqa: F401
from app.models.timeline import Timeline              # noqa: F401

log = structlog.get_logger(__name__)
settings = get_settings()

# ── Synchronous SQLAlchemy engine for Celery workers ──────────────────────────
# Celery workers run in a separate process — use sync engine.
_sync_url = settings.database_url.replace("+aiosqlite", "")
_sync_engine = create_engine(_sync_url, connect_args={"check_same_thread": False})
SyncSession = sessionmaker(bind=_sync_engine, autoflush=False)


def get_sync_db() -> Session:
    return SyncSession()


# ─── Main per-clip analysis task ──────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.analysis_tasks.analyse_clip",
    max_retries=3,
    default_retry_delay=30,
    queue="analysis",
)
def analyse_clip(self, clip_id: str) -> dict:
    """
    Full analysis pipeline for a single clip.
    Called by the API after upload completes.
    """
    log.info("analyse_clip_start", clip_id=clip_id, task_id=self.request.id)
    t_start = time.time()

    db = get_sync_db()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            log.error("clip_not_found", clip_id=clip_id)
            self.update_state(state=states.FAILURE, meta={"error": "Clip not found"})
            raise Ignore()

        # Mark as analysing
        clip.status = "analysing"
        clip.analysis_task_id = self.request.id
        db.commit()

        file_path = clip.file_path

        # ── Steps 1 & 2: CV analysis + Scene detection — run concurrently ────
        self.update_state(state="PROGRESS", meta={"step": "cv_and_scenes", "pct": 10})
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_cv     = pool.submit(analyse_clip_cv, file_path, clip_id)
            fut_scenes = pool.submit(detect_scenes, file_path)
            cv_result  = fut_cv.result()
            scenes     = fut_scenes.result()

        # ── Step 3: Transcription — skip if clip has no audio ─────────────────────
        self.update_state(state="PROGRESS", meta={"step": "transcription", "pct": 55})
        if clip.audio_codec:   # only transcribe if the clip actually has audio
            transcript_data = transcribe_clip(file_path)
        else:
            transcript_data = {"text": "", "segments": [], "language": ""}

        # ── Step 4: LLM tagging (structured metadata only) ────────────────────
        self.update_state(state="PROGRESS", meta={"step": "llm_tagging", "pct": 80})
        tag_meta = {
            **cv_result,
            "duration": clip.duration,
            "width": clip.width,
            "height": clip.height,
            "fps": clip.fps,
            "audio_codec": clip.audio_codec,
            "scene_count": len(scenes),
            "transcript": transcript_data.get("text", ""),
        }
        tag_result = tag_and_summarise(tag_meta)

        # ── Step 5: Persist ───────────────────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"step": "persisting", "pct": 95})
        elapsed = time.time() - t_start

        existing = db.query(ClipAnalysis).filter(ClipAnalysis.clip_id == clip_id).first()
        if existing:
            analysis = existing
        else:
            analysis = ClipAnalysis(clip_id=clip_id)
            db.add(analysis)

        analysis.blur_score = cv_result.get("blur_score")
        analysis.shake_score = cv_result.get("shake_score")
        analysis.exposure_score = cv_result.get("exposure_score")
        analysis.overall_score = cv_result.get("overall_score")
        analysis.is_blurry = cv_result.get("is_blurry", False)
        analysis.is_shaky = cv_result.get("is_shaky", False)
        analysis.is_overexposed = cv_result.get("is_overexposed", False)
        analysis.is_underexposed = cv_result.get("is_underexposed", False)
        analysis.perceptual_hash = cv_result.get("perceptual_hash")
        analysis.usable_ranges = cv_result.get("usable_ranges", [])
        analysis.scene_count = len(scenes)
        analysis.scenes = scenes
        analysis.tags = tag_result.get("tags", [])
        analysis.summary = tag_result.get("summary", "")
        analysis.transcript = transcript_data.get("text", "")
        analysis.transcript_segments = transcript_data.get("segments", [])
        analysis.analysed_at = datetime.now(timezone.utc)
        analysis.analysis_duration_s = round(elapsed, 2)

        # ── Automatically Trim the Best Range ────────────────────────────────
        # Only trim if there are usable ranges. If usable_ranges is empty,
        # the clip has no stable/sharp portions and will be excluded from the
        # timeline. We do NOT fall back to trimming the full clip here.
        try:
            usable_ranges = cv_result.get("usable_ranges", [])
            clip_dur = clip.duration or 0.0

            if usable_ranges:
                # Longest segment = most contiguous good frames = best part
                best_range = max(usable_ranges, key=lambda r: r["end"] - r["start"])
                start_t = best_range["start"]
                end_t   = best_range["end"]
                log.info(
                    "auto_trim_best_range",
                    clip_id=clip_id,
                    start=start_t,
                    end=end_t,
                    total_usable_segments=len(usable_ranges),
                )

                from pathlib import Path
                from app.services.ffmpeg_utils import trim_video
                trimmed_dir = Path(settings.upload_dir).parent / "trimmed" / clip.project_id
                trimmed_dir.mkdir(parents=True, exist_ok=True)
                trimmed_path = trimmed_dir / f"{clip.id}_trimmed.mp4"

                success = trim_video(
                    input_path=file_path,
                    output_path=trimmed_path,
                    start_s=start_t,
                    end_s=end_t,
                    transcode=False   # stream-copy for fast preview
                )
                if success:
                    clip.trimmed_file_path = str(trimmed_path)
                    log.info("auto_trimming_done", clip_id=clip_id, path=str(trimmed_path),
                             start=start_t, end=end_t)
                else:
                    log.warning("auto_trimming_failed", clip_id=clip_id)
            else:
                log.info(
                    "auto_trim_skipped",
                    clip_id=clip_id,
                    reason="no_usable_ranges_clip_is_all_bad_quality",
                )
        except Exception as trim_exc:
            log.warning("auto_trimming_exception", clip_id=clip_id, error=str(trim_exc))

        clip.status = "analysed"
        db.commit()

        log.info("analyse_clip_done", clip_id=clip_id, elapsed=elapsed)
        return {
            "clip_id": clip_id,
            "score": analysis.overall_score,
            "tags": analysis.tags,
            "summary": analysis.summary,
            "duration_s": elapsed,
        }

    except Exception as exc:
        db.rollback()
        import traceback
        traceback.print_exc()
        log.error("analyse_clip_error", clip_id=clip_id, error=str(exc))
        # Mark clip as error
        try:
            clip_obj = db.query(Clip).filter(Clip.id == clip_id).first()
            if clip_obj:
                clip_obj.status = "error"
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()


# ─── Batch analysis task ──────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.analysis_tasks.analyse_project",
    queue="analysis",
)
def analyse_project(self, project_id: str) -> dict:
    """
    Trigger analysis for all uploaded clips in a project.
    Returns immediately; individual clip tasks run in parallel.
    """

    db = get_sync_db()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {"error": "Project not found"}

        clips = (
            db.query(Clip)
            .filter(
                Clip.project_id == project_id,
                Clip.status.in_(["uploaded", "error", "analysing"])
            )
            .all()
        )

        task_ids = []
        for clip in clips:
            task = analyse_clip.apply_async(args=[clip.id])
            clip.analysis_task_id = task.id
            task_ids.append(task.id)

        project.status = "analysing"
        db.commit()

        log.info("project_analysis_dispatched", project_id=project_id, clip_count=len(clips))
        return {"project_id": project_id, "dispatched": len(clips), "task_ids": task_ids}
    finally:
        db.close()


# ─── Duplicate detection (runs after all clips analysed) ─────────────────────

@celery_app.task(
    name="app.workers.analysis_tasks.detect_project_duplicates",
    queue="analysis",
)
def detect_project_duplicates(project_id: str) -> dict:
    """Find and mark duplicate clips within a project using perceptual hashing."""
    db = get_sync_db()
    try:
        analyses = (
            db.query(ClipAnalysis)
            .join(Clip, Clip.id == ClipAnalysis.clip_id)
            .filter(Clip.project_id == project_id)
            .all()
        )

        hashes = {
            a.clip_id: a.perceptual_hash
            for a in analyses
            if a.perceptual_hash
        }

        from app.ai.cv_analyser import find_duplicates
        pairs = find_duplicates(hashes)

        for clip_id_a, clip_id_b in pairs:
            dup = db.query(ClipAnalysis).filter(ClipAnalysis.clip_id == clip_id_b).first()
            if dup:
                dup.has_duplicate = True
                dup.duplicate_of_clip_id = clip_id_a

        db.commit()
        log.info("duplicates_detected", project_id=project_id, pairs=len(pairs))
        return {"project_id": project_id, "duplicate_pairs": len(pairs)}
    finally:
        db.close()
