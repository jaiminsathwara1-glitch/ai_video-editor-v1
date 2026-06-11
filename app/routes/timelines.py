"""
Timeline router — generate rough-cut timeline, retrieve, export.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.timeline import Timeline
from app.schemas.timeline import TimelineCreate, TimelineRead
from app.services.timeline_service import generate_timeline

router = APIRouter(prefix="/timelines", tags=["Timelines"])


# ── AI Reorder entries ────────────────────────────────────────────────────────

@router.post("/{timeline_id}/reorder", response_model=TimelineRead)
async def ai_reorder(
    timeline_id: str,
    analysis_mode: str = "gemini",
    db: AsyncSession = Depends(get_db),
) -> TimelineRead:
    """
    Re-sequence the existing timeline entries using AI (Groq/OpenAI).
    Preserves all trim points (in_point / out_point) and locked status.
    Only changes the order of the entries.
    """
    from sqlalchemy import select as sa_select
    from app.models.clip import Clip
    from app.models.analysis import ClipAnalysis
    from app.ai.llm_scorer import suggest_sequence

    result = await db.execute(sa_select(Timeline).where(Timeline.id == timeline_id))
    timeline = result.scalar_one_or_none()
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    entries = timeline.entries or []
    if not entries:
        raise HTTPException(status_code=400, detail="Timeline has no entries to reorder")

    # Fetch analysis metadata for each clip in the current timeline
    clip_ids = [e["clip_id"] for e in entries]
    clips_result = await db.execute(
        sa_select(Clip, ClipAnalysis)
        .join(ClipAnalysis, ClipAnalysis.clip_id == Clip.id)
        .where(Clip.id.in_(clip_ids))
    )
    rows = clips_result.all()
    meta_by_id = {
        clip.id: {
            "clip_id": clip.id,
            "filename": clip.original_filename or "",   # key for room classification
            "duration": clip.duration,
            "fps": clip.fps,
            "width": clip.width,
            "height": clip.height,
            "overall_score": analysis.overall_score,
            "blur_score": analysis.blur_score,
            "shake_score": analysis.shake_score,
            "exposure_score": analysis.exposure_score,
            "tags": analysis.tags or [],
            "summary": analysis.summary or "",
            "transcript": analysis.transcript or "",
            "scene_count": analysis.scene_count,
            "usable_ranges": analysis.usable_ranges or [],
        }
        for clip, analysis in rows
    }

    # Build the metadata list preserving existing entry order as context
    clips_meta = [meta_by_id[cid] for cid in clip_ids if cid in meta_by_id]

    if not clips_meta:
        raise HTTPException(status_code=400, detail="No analysis data found for timeline clips")

    # Run AI sequencing
    import asyncio
    loop = asyncio.get_running_loop()
    sequence = await loop.run_in_executor(None, suggest_sequence, clips_meta, analysis_mode)

    # Map the new AI order back onto the existing entries (preserving trim pts)
    order_map = {item["clip_id"]: item["order"] for item in sequence}
    reason_map = {item["clip_id"]: item.get("reason", "") for item in sequence}

    entry_by_clip = {e["clip_id"]: e for e in entries}
    new_entries = sorted(
        [
            {
                **entry_by_clip[cid],
                "order": order_map.get(cid, 999),
                "reason": reason_map.get(cid, ""),
            }
            for cid in clip_ids
            if cid in entry_by_clip
        ],
        key=lambda e: e["order"],
    )
    # Re-index orders cleanly 1, 2, 3 ...
    for i, e in enumerate(new_entries):
        e["order"] = i + 1

    timeline.entries = new_entries
    await db.commit()
    await db.refresh(timeline)

    return TimelineRead.model_validate(timeline)


# ── Generate timeline ─────────────────────────────────────────────────────────

@router.post("/generate", response_model=TimelineRead, status_code=status.HTTP_201_CREATED)
async def create_timeline(
    body: TimelineCreate,
    db: AsyncSession = Depends(get_db),
) -> TimelineRead:
    """
    Generate an AI-assisted rough-cut timeline for a project.
    Clips must be analysed before calling this endpoint.
    """
    try:
        timeline = await generate_timeline(
            db=db,
            project_id=body.project_id,
            name=body.name,
            min_score=body.min_score,
            target_duration=body.target_duration,
            analysis_mode=body.analysis_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return TimelineRead.model_validate(timeline)


# ── Get timeline ──────────────────────────────────────────────────────────────

@router.get("/{timeline_id}", response_model=TimelineRead)
async def get_timeline(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> TimelineRead:
    result = await db.execute(select(Timeline).where(Timeline.id == timeline_id))
    timeline = result.scalar_one_or_none()
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return TimelineRead.model_validate(timeline)


# ── List timelines for project ────────────────────────────────────────────────

@router.get("/project/{project_id}", response_model=list[TimelineRead])
async def list_timelines(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[TimelineRead]:
    result = await db.execute(
        select(Timeline)
        .where(Timeline.project_id == project_id)
        .order_by(Timeline.created_at.desc())
    )
    timelines = result.scalars().all()
    return [TimelineRead.model_validate(t) for t in timelines]


# ── Export XML (Adobe Premiere) ───────────────────────────────────────────────

@router.post("/{timeline_id}/export/xml", status_code=status.HTTP_202_ACCEPTED)
async def export_xml(
    timeline_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger background export to FCP XML (Premiere-compatible)."""
    result = await db.execute(select(Timeline).where(Timeline.id == timeline_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Timeline not found")

    from app.workers.export_tasks import export_timeline
    task = export_timeline.apply_async(args=[timeline_id, ["xml"]])
    return {"timeline_id": timeline_id, "task_id": task.id, "format": "xml", "status": "queued"}


# ── Export EDL ────────────────────────────────────────────────────────────────

@router.post("/{timeline_id}/export/edl", status_code=status.HTTP_202_ACCEPTED)
async def export_edl(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger background export to CMX 3600 EDL."""
    result = await db.execute(select(Timeline).where(Timeline.id == timeline_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Timeline not found")

    from app.workers.export_tasks import export_timeline
    task = export_timeline.apply_async(args=[timeline_id, ["edl"]])
    return {"timeline_id": timeline_id, "task_id": task.id, "format": "edl", "status": "queued"}


# ── Export all formats at once ────────────────────────────────────────────────

@router.post("/{timeline_id}/export/all", status_code=status.HTTP_202_ACCEPTED)
async def export_all(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export XML + EDL + OTIO in a single background task."""
    result = await db.execute(select(Timeline).where(Timeline.id == timeline_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Timeline not found")

    from app.workers.export_tasks import export_timeline
    task = export_timeline.apply_async(args=[timeline_id, ["xml", "edl", "otio"]])
    return {
        "timeline_id": timeline_id,
        "task_id": task.id,
        "formats": ["xml", "edl", "otio"],
        "status": "queued",
    }


# ── Download rendered video ───────────────────────────────────────────────────

@router.get("/{timeline_id}/download/video")
async def download_video(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the rendered rough-cut video."""
    result = await db.execute(select(Timeline).where(Timeline.id == timeline_id))
    timeline = result.scalar_one_or_none()
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if not timeline.render_video_path:
        raise HTTPException(
            status_code=404,
            detail="Rendered video not found. Did you trigger the video render?",
        )

    from pathlib import Path
    if not Path(timeline.render_video_path).exists():
        raise HTTPException(status_code=404, detail="Rendered video file missing from disk.")

    return FileResponse(
        path=timeline.render_video_path,
        media_type="video/mp4",
        filename=f"timeline_{timeline_id}.mp4",
    )


# ── Download exported file ────────────────────────────────────────────────────

@router.get("/{timeline_id}/download/{fmt}")
async def download_export(
    timeline_id: str,
    fmt: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download an already-exported file. fmt: xml | edl | otio"""
    result = await db.execute(select(Timeline).where(Timeline.id == timeline_id))
    timeline = result.scalar_one_or_none()
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    path_map = {
        "xml": timeline.xml_export_path,
        "edl": timeline.edl_export_path,
        "otio": timeline.otio_export_path,
    }
    file_path = path_map.get(fmt)
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail=f"Export '{fmt}' not found. Did you trigger the export?",
        )

    from pathlib import Path
    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Export file missing from disk.")

    media_type_map = {
        "xml": "application/xml",
        "edl": "text/plain",
        "otio": "application/json",
    }
    return FileResponse(
        path=file_path,
        media_type=media_type_map.get(fmt, "application/octet-stream"),
        filename=f"timeline_{timeline_id}.{fmt}",
    )


# ── Export/Render Video ───────────────────────────────────────────────────────

@router.post("/{timeline_id}/render", status_code=status.HTTP_202_ACCEPTED)
async def render_video(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger background video render/concat for this rough-cut timeline."""
    result = await db.execute(select(Timeline).where(Timeline.id == timeline_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Timeline not found")

    from app.workers.export_tasks import render_timeline_video
    task = render_timeline_video.apply_async(args=[timeline_id])
    return {
        "timeline_id": timeline_id,
        "task_id": task.id,
        "status": "queued",
    }

