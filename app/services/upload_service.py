"""
Upload service — handles chunked / resumable uploads.

Flow:
1. Client calls POST /clips/upload/init  → gets clip_id + upload_url
2. Client PUTs binary chunks to POST /clips/{clip_id}/chunk/{index}
3. When all chunks received, service assembles the file and triggers metadata extraction
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import AsyncIterator

import aiofiles
import structlog
import httpx
import zipfile
import tempfile
import os
from urllib.parse import urlparse
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.config import get_settings
from app.models.clip import Clip, ClipChunk
from app.services.ffmpeg_utils import extract_metadata_async, generate_thumbnails_async

log = structlog.get_logger(__name__)
settings = get_settings()


# ─── Init upload session ──────────────────────────────────────────────────────

async def init_upload(
    db: AsyncSession,
    project_id: str,
    filename: str,
    file_size: int,
    mime_type: str,
    total_chunks: int,
) -> Clip:
    """Create a Clip record and prepare chunk staging directory."""
    clip = Clip(
        project_id=project_id,
        filename=filename,
        original_filename=filename,
        file_path="",          # filled after assembly
        file_size=file_size,
        mime_type=mime_type,
        status="uploading",
    )
    db.add(clip)
    await db.flush()            # get ID without commit

    # Create staging directory for chunks
    staging_dir = _chunk_dir(clip.id)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Store total_chunks as a sentinel file for recovery
    (staging_dir / ".total_chunks").write_text(str(total_chunks))

    log.info("upload_session_created", clip_id=clip.id, filename=filename)
    return clip


# ─── Receive one chunk ────────────────────────────────────────────────────────

async def receive_chunk(
    db: AsyncSession,
    clip_id: str,
    chunk_index: int,
    data: bytes,
) -> dict:
    """Save a chunk, return status. Assembles file if all chunks received."""
    chunk_path = _chunk_dir(clip_id) / f"chunk_{chunk_index:06d}.bin"
    async with aiofiles.open(chunk_path, "wb") as f:
        await f.write(data)

    # Record chunk in DB (idempotent upsert)
    existing = await db.execute(
        select(ClipChunk).where(
            ClipChunk.clip_id == clip_id,
            ClipChunk.chunk_index == chunk_index,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(ClipChunk(clip_id=clip_id, chunk_index=chunk_index, chunk_path=str(chunk_path)))
        await db.flush()

    # Count received chunks
    result = await db.execute(
        select(ClipChunk).where(ClipChunk.clip_id == clip_id)
    )
    received = len(result.scalars().all())

    total_chunks = _read_total_chunks(clip_id)
    is_complete = received >= total_chunks

    if is_complete:
        await _assemble_clip(db, clip_id)

    return {
        "clip_id": clip_id,
        "chunk_index": chunk_index,
        "received_chunks": received,
        "total_chunks": total_chunks,
        "is_complete": is_complete,
    }


# ─── Simple (non-chunked) upload for smaller files ────────────────────────────

async def receive_simple_upload(
    db: AsyncSession,
    project_id: str,
    file: UploadFile,
) -> Clip:
    """Stream an entire UploadFile directly to disk."""
    filename = file.filename or "upload.mp4"
    clip = Clip(
        project_id=project_id,
        filename=filename,
        original_filename=filename,
        file_path="",
        mime_type=file.content_type or "video/mp4",
        status="uploading",
    )
    db.add(clip)
    await db.flush()

    dest_path = settings.upload_dir / clip.project_id / f"{clip.id}_{filename}"
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    CHUNK = 1024 * 1024 * 8   # 8 MB read buffer
    async with aiofiles.open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            await out.write(chunk)
            size += len(chunk)

    clip.file_path = str(dest_path)
    clip.file_size = size

    await _finalize_clip(db, clip)
    return clip


# ─── URL upload ───────────────────────────────────────────────────────────────

async def receive_url_upload(
    db: AsyncSession,
    project_id: str,
    url: str,
    placeholder_clip: Clip | None = None,
) -> list[Clip]:
    """Download a video file (or a ZIP folder of videos) from a URL directly to disk."""
    if "dropbox.com" in url and "dl=0" in url:
        url = url.replace("dl=0", "dl=1")
        
    parsed = urlparse(url)
    filename = parsed.path.split("/")[-1]
    if not filename or '.' not in filename:
        filename = "download.zip" if "dropbox.com" in url else "downloaded_video.mp4"

    # Download to a temporary file first
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=settings.temp_dir) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60.0)) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                # Check if the server says it's a zip
                content_type = response.headers.get("content-type", "")
                total_size = int(response.headers.get("content-length", 0))
                
                if "application/zip" in content_type and not filename.endswith(".zip"):
                    filename += ".zip"
                
                async with aiofiles.open(tmp_path, "wb") as out:
                    size = 0
                    last_update_size = 0
                    async for chunk in response.aiter_bytes(chunk_size=1024*1024*8):
                        if chunk:
                            await out.write(chunk)
                            size += len(chunk)
                            if placeholder_clip and (size - last_update_size > 50_000_000):
                                downloaded_mb = size // (1024 * 1024)
                                if total_size > 0:
                                    total_mb = total_size // (1024 * 1024)
                                    placeholder_clip.original_filename = f"Downloading Archive... ({downloaded_mb}MB / {total_mb}MB)"
                                else:
                                    placeholder_clip.original_filename = f"Downloading Archive... ({downloaded_mb} MB)"
                                await db.commit()
                                last_update_size = size
                                
        if placeholder_clip:
            placeholder_clip.original_filename = "Extracting Archive... Please wait."
            await db.commit()
            
        # Now process the downloaded file
        clips_created = []
        
        if filename.lower().endswith(".zip") or zipfile.is_zipfile(tmp_path):
            # Extract ZIP
            with tempfile.TemporaryDirectory(dir=settings.temp_dir) as extract_dir:
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                    
                # Find all video files
                valid_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
                for root, _, files in os.walk(extract_dir):
                    for file in files:
                        ext = Path(file).suffix.lower()
                        if ext in valid_exts and not file.startswith('._'):
                            extracted_path = Path(root) / file
                            clip = await _create_clip_from_file(db, project_id, file, extracted_path)
                            clips_created.append(clip)
        else:
            # Single video file
            clip = await _create_clip_from_file(db, project_id, filename, tmp_path)
            clips_created.append(clip)
            
        return clips_created
        
    except Exception as e:
        log.error("url_download_failed", url=url, error=str(e))
        raise
    finally:
        tmp_path.unlink(missing_ok=True)


async def receive_url_upload_background(project_id: str, url: str) -> None:
    """Wrapper to run URL upload in a FastAPI BackgroundTask with its own DB session."""
    log.info("background_url_upload_started", url=url)
    async with AsyncSessionLocal() as db:
        # Create a placeholder clip so the user sees progress in the UI
        placeholder = Clip(
            project_id=project_id,
            filename="Downloading Archive...",
            original_filename="Downloading & Extracting Archive...",
            mime_type="application/zip",
            status="uploading",
            file_path="",
        )
        db.add(placeholder)
        await db.commit()
        await db.refresh(placeholder)

        try:
            await receive_url_upload(db, project_id, url, placeholder_clip=placeholder)
            log.info("background_url_upload_finished", url=url)
            # Remove placeholder and commit the real clips
            await db.delete(placeholder)
            await db.commit()
        except Exception as e:
            await db.rollback()
            placeholder.status = "error"
            db.add(placeholder)
            await db.commit()
            log.error("background_url_upload_error", url=url, error=str(e))


async def _create_clip_from_file(db: AsyncSession, project_id: str, original_filename: str, source_path: Path) -> Clip:
    """Helper to move a file to the project folder and create a Clip."""
    clip = Clip(
        project_id=project_id,
        filename=original_filename,
        original_filename=original_filename,
        file_path="",
        mime_type="video/mp4",
        status="uploading",
    )
    db.add(clip)
    await db.flush()

    dest_path = settings.upload_dir / project_id / f"{clip.id}_{original_filename}"
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Move or copy file
    import shutil
    shutil.copy2(source_path, dest_path)
    
    clip.file_path = str(dest_path)
    clip.file_size = dest_path.stat().st_size
    
    await _finalize_clip(db, clip)
    return clip


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _assemble_clip(db: AsyncSession, clip_id: str) -> None:
    """Concatenate all chunks into the final file."""
    result = await db.execute(
        select(Clip).where(Clip.id == clip_id)
    )
    clip = result.scalar_one_or_none()
    if not clip:
        log.error("clip_not_found_on_assemble", clip_id=clip_id)
        return

    staging_dir = _chunk_dir(clip_id)
    chunks = sorted(staging_dir.glob("chunk_*.bin"))

    dest_path = settings.upload_dir / clip.project_id / f"{clip_id}_{clip.original_filename}"
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(dest_path, "wb") as out:
        for chunk_file in chunks:
            async with aiofiles.open(chunk_file, "rb") as cf:
                await out.write(await cf.read())

    clip.file_path = str(dest_path)

    await _finalize_clip(db, clip)

    # Clean up staging
    shutil.rmtree(staging_dir, ignore_errors=True)
    log.info("clip_assembled", clip_id=clip_id, path=str(dest_path))


async def _finalize_clip(db: AsyncSession, clip: Clip) -> None:
    """Extract metadata and generate thumbnail after upload is complete."""
    try:
        meta = await extract_metadata_async(clip.file_path)
        clip.duration = meta["duration"]
        clip.width = meta["width"]
        clip.height = meta["height"]
        clip.fps = meta["fps"]
        clip.video_codec = meta["video_codec"]
        clip.audio_codec = meta["audio_codec"]
        clip.bit_rate = meta["bit_rate"]
        clip.nb_frames = meta["nb_frames"]
        clip.raw_metadata = meta["raw_metadata"]
    except Exception as exc:
        log.warning("metadata_extract_failed", clip_id=clip.id, error=str(exc))

    try:
        thumb_paths = await generate_thumbnails_async(
            clip.file_path,
            settings.thumbnail_dir / clip.project_id,
            clip.id,
            count=settings.thumbnail_count,
            width=settings.thumbnail_width,
            height=settings.thumbnail_height,
        )
        if thumb_paths:
            clip.thumbnail_path = str(thumb_paths[0])
    except Exception as exc:
        log.warning("thumbnail_gen_failed", clip_id=clip.id, error=str(exc))

    clip.status = "uploaded"
    await db.flush()


def _chunk_dir(clip_id: str) -> Path:
    return settings.temp_dir / "chunks" / clip_id


def _read_total_chunks(clip_id: str) -> int:
    sentinel = _chunk_dir(clip_id) / ".total_chunks"
    try:
        return int(sentinel.read_text().strip())
    except Exception:
        return 999_999   # fallback — never auto-assemble
