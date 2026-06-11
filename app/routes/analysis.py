"""
Analysis router — start analysis, query status, get scores.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.clip import Clip
from app.models.analysis import ClipAnalysis
from app.schemas.analysis import AnalysisRead
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/analysis", tags=["Analysis"])


# ── Start analysis for a single clip ─────────────────────────────────────────

@router.post("/clip/{clip_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_clip_analysis(
    clip_id: str,
    analysis_mode: str = "gemini",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dispatch analysis task for one clip."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    if clip.status not in ("uploaded", "error", "analysing", "analysed"):
        raise HTTPException(
            status_code=400,
            detail=f"Clip is in state '{clip.status}'. Must be 'uploaded', 'error', 'analysing', or 'analysed' to start analysis.",
        )

    from app.workers.analysis_tasks import analyse_clip
    task = analyse_clip.apply_async(args=[clip_id], kwargs={"analysis_mode": analysis_mode})

    clip.analysis_task_id = task.id
    clip.status = "analysing"
    await db.flush()

    return {"clip_id": clip_id, "task_id": task.id, "status": "queued"}



# ── Start analysis for all clips in a project ─────────────────────────────────

@router.post("/project/{project_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_project_analysis(
    project_id: str,
    analysis_mode: str = "gemini",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dispatch analysis for all uploaded clips in a project."""
    from app.workers.analysis_tasks import analyse_project
    task = analyse_project.apply_async(args=[project_id], kwargs={"analysis_mode": analysis_mode})
    return {"project_id": project_id, "task_id": task.id, "status": "queued"}


# ── Get analysis status (Celery task) ────────────────────────────────────────

@router.get("/task/{task_id}/status")
async def get_task_status(task_id: str) -> dict:
    """Poll Celery task status."""
    task = celery_app.AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": task.status,
        "result": None,
        "progress": None,
    }
    if task.status == "PROGRESS":
        response["progress"] = task.info
    elif task.status == "SUCCESS":
        response["result"] = task.result
    elif task.status == "FAILURE":
        response["result"] = str(task.result)
    return response


# ── Get clip analysis results ─────────────────────────────────────────────────

@router.get("/clip/{clip_id}", response_model=AnalysisRead)
async def get_clip_analysis(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisRead:
    """Return the analysis results for a clip."""
    result = await db.execute(
        select(ClipAnalysis).where(ClipAnalysis.clip_id == clip_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found. Has the clip been analysed?",
        )
    return AnalysisRead.model_validate(analysis)


# ── Get all clip scores for a project ────────────────────────────────────────

@router.get("/project/{project_id}/scores")
async def get_project_scores(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Return a summary of all clip scores for a project.
    Matches the example output format from the spec.
    """
    result = await db.execute(
        select(Clip, ClipAnalysis)
        .join(ClipAnalysis, ClipAnalysis.clip_id == Clip.id)
        .where(Clip.project_id == project_id)
        .order_by((ClipAnalysis.overall_score).desc())
    )
    rows = result.all()

    scores = []
    for clip, analysis in rows:
        scores.append(
            {
                "clip_id": clip.id,
                "filename": clip.original_filename,
                "score": analysis.overall_score,
                "overall_score": analysis.overall_score,
                "usable_ranges": analysis.usable_ranges or [],
                "tags": analysis.tags or [],
                "summary": analysis.summary or "",
                "is_blurry": analysis.is_blurry,
                "is_shaky": analysis.is_shaky,
                "is_overexposed": analysis.is_overexposed,
                "is_underexposed": analysis.is_underexposed,
                "has_duplicate": analysis.has_duplicate,
            }
        )

    return scores


# ── Detect duplicates across a project ───────────────────────────────────────

@router.post("/project/{project_id}/duplicates", status_code=status.HTTP_202_ACCEPTED)
async def detect_duplicates(project_id: str) -> dict:
    from app.workers.analysis_tasks import detect_project_duplicates
    task = detect_project_duplicates.apply_async(args=[project_id])
    return {"project_id": project_id, "task_id": task.id, "status": "queued"}
