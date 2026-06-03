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
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
