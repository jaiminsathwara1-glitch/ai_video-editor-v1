"""
Clips router — upload (chunked & simple), metadata, list.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.clip import Clip
from app.schemas.clip import ClipRead, ClipUploadInit, ChunkUploadResponse, ClipUrlUpload
from app.services.upload_service import init_upload, receive_chunk, receive_simple_upload, receive_url_upload

router = APIRouter(prefix="/clips", tags=["Clips"])


# ── 1. Initialise chunked upload session ──────────────────────────────────────

@router.post("/upload/init", response_model=ClipRead, status_code=status.HTTP_201_CREATED)
async def init_chunked_upload(
    body: ClipUploadInit,
    db: AsyncSession = Depends(get_db),
) -> ClipRead:
    """
    Start a resumable chunked upload.
    Returns a clip_id to use for subsequent chunk uploads.
    """
    clip = await init_upload(
        db=db,
        project_id=body.project_id,
        filename=body.filename,
        file_size=body.file_size,
        mime_type=body.mime_type,
        total_chunks=body.total_chunks,
    )
    return ClipRead.model_validate(clip)


# ── 2. Upload one chunk ───────────────────────────────────────────────────────

@router.post("/{clip_id}/chunk/{chunk_index}", response_model=ChunkUploadResponse)
async def upload_chunk(
    clip_id: str,
    chunk_index: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ChunkUploadResponse:
    """
    Upload a single binary chunk.
    Body must be raw binary (Content-Type: application/octet-stream).
    """
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Empty chunk body")

    result = await receive_chunk(db=db, clip_id=clip_id, chunk_index=chunk_index, data=data)
    return ChunkUploadResponse(**result)


# ── 3. Simple (non-chunked) upload for smaller files ─────────────────────────

@router.post("/upload/simple", response_model=ClipRead, status_code=status.HTTP_201_CREATED)
async def simple_upload(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ClipRead:
    """Upload a single video file directly (suitable for files < ~1 GB)."""
    clip = await receive_simple_upload(db=db, project_id=project_id, file=file)
    return ClipRead.model_validate(clip)


@router.post("/upload/url", response_model=list[ClipRead], status_code=status.HTTP_202_ACCEPTED)
async def url_upload(
    body: ClipUrlUpload,
    background_tasks: BackgroundTasks,
) -> list[ClipRead]:
    """Queue a download and upload a video file (or a folder ZIP) from a given URL in the background."""
    from app.services.upload_service import receive_url_upload_background
    background_tasks.add_task(receive_url_upload_background, body.project_id, body.url)
    return []


# ── 4. Global AI Search ────────────────────────────────────────────────────────

from app.ai.search import semantic_search_clips

@router.get("/search/global")
async def global_search_clips(
    q: str,
    top_k: int = 12,
    db: AsyncSession = Depends(get_db),
):
    """
    Search for clips using natural language semantics across all projects.
    Returns the top matching clips based on vector embeddings, including their analysis.
    """
    if not q:
        return []
    results = await semantic_search_clips(db, q, top_k)
    
    out = []
    for item in results:
        clip = item["clip"]
        score = item["score"]
        analysis = clip.analysis
        
        # Serialize the clip
        clip_dict = ClipRead.model_validate(clip).model_dump(mode='json')
        
        # Include necessary analysis fields for the frontend
        analysis_dict = {}
        if analysis:
            analysis_dict = {
                "tags": analysis.tags or [],
                "summary": analysis.summary or "",
                "overall_score": analysis.overall_score,
                "is_blurry": analysis.is_blurry,
                "is_shaky": analysis.is_shaky,
                "is_overexposed": analysis.is_overexposed,
                "is_underexposed": analysis.is_underexposed,
                "has_duplicate": analysis.has_duplicate
            }
            
        out.append({
            "clip": clip_dict,
            "analysis": analysis_dict,
            "search_score": score
        })
        
    return out


# ── 5. List clips in project ──────────────────────────────────────────────────

@router.get("/project/{project_id}", response_model=list[ClipRead])
async def list_clips(
    project_id: str,
    status_filter: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[ClipRead]:
    q = select(Clip).where(Clip.project_id == project_id)
    if status_filter:
        q = q.where(Clip.status == status_filter)
    q = q.order_by(Clip.created_at.asc()).offset(skip).limit(limit)

    result = await db.execute(q)
    clips = result.scalars().all()
    return [ClipRead.model_validate(c) for c in clips]


# ── 5. Single clip detail ─────────────────────────────────────────────────────

@router.get("/{clip_id}", response_model=ClipRead)
async def get_clip(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
) -> ClipRead:
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return ClipRead.model_validate(clip)


# ── 6. Delete clip ────────────────────────────────────────────────────────────

@router.delete("/{clip_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_clip(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Clean up physical files from disk
    from pathlib import Path
    for path_str in (clip.file_path, clip.thumbnail_path, clip.trimmed_file_path):
        if path_str:
            try:
                Path(path_str).unlink(missing_ok=True)
            except Exception:
                pass

    await db.delete(clip)


# ── 7. Get clip thumbnail ─────────────────────────────────────────────────────

@router.get("/{clip_id}/thumbnail")
async def get_clip_thumbnail(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the generated thumbnail for the clip."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip or not clip.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    from pathlib import Path
    from fastapi.responses import FileResponse
    if not Path(clip.thumbnail_path).exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing from disk")

    return FileResponse(clip.thumbnail_path, media_type="image/jpeg")


# ── 8. Get trimmed video preview ──────────────────────────────────────────────

@router.get("/{clip_id}/trimmed")
async def get_clip_trimmed_video(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the auto-trimmed video preview file."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip or not clip.trimmed_file_path:
        raise HTTPException(status_code=404, detail="Trimmed video not found")

    from pathlib import Path
    from fastapi.responses import FileResponse
    if not Path(clip.trimmed_file_path).exists():
        raise HTTPException(status_code=404, detail="Trimmed video file missing from disk")

    return FileResponse(clip.trimmed_file_path, media_type="video/mp4")
