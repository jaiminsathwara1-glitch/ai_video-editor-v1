"""
Celery export tasks — run OTIO/EDL export in background.
"""
from __future__ import annotations

import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)
settings = get_settings()

_sync_url = settings.database_url.replace("+aiosqlite", "")
_sync_engine = create_engine(_sync_url, connect_args={"check_same_thread": False})
SyncSession = sessionmaker(bind=_sync_engine, autoflush=False)


@celery_app.task(
    bind=True,
    name="app.workers.export_tasks.export_timeline",
    queue="export",
)
def export_timeline(self, timeline_id: str, formats: list[str] | None = None) -> dict:
    """
    Export a timeline to XML, EDL, and/or OTIO.
    formats: list of "xml", "edl", "otio" — defaults to all three.
    """
    from app.models.timeline import Timeline
    from app.models.clip import Clip
    from app.services.otio_exporter import (
        build_otio_timeline,
        export_fcp_xml,
        export_edl,
        export_otio,
    )

    formats = formats or ["xml", "edl", "otio"]
    db = SyncSession()

    try:
        timeline = db.query(Timeline).filter(Timeline.id == timeline_id).first()
        if not timeline:
            return {"error": "Timeline not found"}

        entries = timeline.entries or []

        # Build clip metadata lookup
        clip_ids = list({e["clip_id"] for e in entries})
        clips = db.query(Clip).filter(Clip.id.in_(clip_ids)).all()
        clips_meta = {
            c.id: {
                "file_path": c.file_path,
                "fps": c.fps or 24.0,
                "duration": c.duration or 0,
                "width": c.width,
                "height": c.height,
            }
            for c in clips
        }

        # Build OTIO timeline
        otio_tl = build_otio_timeline(
            timeline_name=timeline.name,
            entries=entries,
            clips_meta=clips_meta,
        )

        export_dir = settings.export_dir / timeline.project_id
        result = {}

        if "xml" in formats:
            self.update_state(state="PROGRESS", meta={"step": "xml"})
            p = export_fcp_xml(otio_tl, export_dir / f"{timeline_id}.xml")
            timeline.xml_export_path = str(p)
            result["xml"] = str(p)

        if "edl" in formats:
            self.update_state(state="PROGRESS", meta={"step": "edl"})
            p = export_edl(otio_tl, export_dir / f"{timeline_id}.edl")
            timeline.edl_export_path = str(p)
            result["edl"] = str(p)

        if "otio" in formats:
            self.update_state(state="PROGRESS", meta={"step": "otio"})
            p = export_otio(otio_tl, export_dir / f"{timeline_id}.otio")
            timeline.otio_export_path = str(p)
            result["otio"] = str(p)

        db.commit()
        log.info("export_complete", timeline_id=timeline_id, formats=formats)
        return result

    except Exception as exc:
        db.rollback()
        log.error("export_failed", timeline_id=timeline_id, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.workers.export_tasks.render_timeline_video",
    queue="export",
)
def render_timeline_video(self, timeline_id: str) -> dict:
    """
    Render/compile a rough-cut timeline into a single MP4 video.
    """
    from app.models.timeline import Timeline
    from app.models.clip import Clip
    from app.services.ffmpeg_utils import trim_video, concat_clips
    from pathlib import Path

    log.info("render_timeline_video_start", timeline_id=timeline_id)
    db = SyncSession()
    temp_files = []

    try:
        timeline = db.query(Timeline).filter(Timeline.id == timeline_id).first()
        if not timeline:
            return {"error": "Timeline not found"}

        entries = sorted(timeline.entries or [], key=lambda e: e.get("order", 0))
        if not entries:
            return {"error": "Timeline is empty"}

        # Stage 1: Trim all clip segments to temp directory
        self.update_state(state="PROGRESS", meta={"step": "trimming_clips", "pct": 10})
        for idx, entry in enumerate(entries):
            clip = db.query(Clip).filter(Clip.id == entry["clip_id"]).first()
            if not clip:
                log.warning("clip_missing_during_render", clip_id=entry["clip_id"])
                continue

            temp_segment = Path(settings.temp_dir) / f"{timeline_id}_seg_{entry['order']}_{idx}.mp4"
            temp_files.append(temp_segment)

            log.info("rendering_trim_segment", clip_id=clip.id, in_point=entry["in_point"], out_point=entry["out_point"])
            success = trim_video(
                input_path=clip.file_path,
                output_path=temp_segment,
                start_s=entry["in_point"],
                end_s=entry["out_point"],
                transcode=True
            )
            if not success:
                raise RuntimeError(f"Failed to trim clip {clip.id} for timeline render")

            # Update progress
            pct = 10 + int((idx + 1) / len(entries) * 70)
            self.update_state(state="PROGRESS", meta={"step": f"trimmed_{idx+1}_of_{len(entries)}", "pct": pct})

        # Stage 2: Concatenate segments into final export
        self.update_state(state="PROGRESS", meta={"step": "concatenating_segments", "pct": 85})
        
        output_dir = settings.export_dir / timeline.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{timeline_id}_render.mp4"

        log.info("rendering_concatenate_start", output_path=str(output_path))
        # All temp_segments are H.264/AAC @1280x720/30fps (from trim_video transcode=True),
        # so stream-copy concat is safe and exact — no re-encoding needed here.
        concat_success = concat_clips(
            clip_paths=temp_files,
            output_path=output_path,
            use_copy=True
        )
        if not concat_success:
            raise RuntimeError("Failed to concatenate segments into final rough-cut video")

        timeline.render_video_path = str(output_path)
        db.commit()

        log.info("render_timeline_video_success", timeline_id=timeline_id, path=str(output_path))
        return {"timeline_id": timeline_id, "render_video_path": str(output_path)}

    except Exception as exc:
        db.rollback()
        log.error("render_timeline_video_failed", timeline_id=timeline_id, error=str(exc))
        raise
    finally:
        db.close()
        # Clean up temporary segments
        for p in temp_files:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
