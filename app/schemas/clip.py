from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class ClipUploadInit(BaseModel):
    """Client sends this to start a resumable upload session."""
    project_id: str
    filename: str
    file_size: int = Field(..., gt=0)
    mime_type: str = "video/mp4"
    total_chunks: int = Field(..., gt=0)


class ChunkUploadResponse(BaseModel):
    clip_id: str
    chunk_index: int
    received_chunks: int
    total_chunks: int
    is_complete: bool


class ClipRead(BaseModel):
    id: str
    project_id: str
    filename: str
    original_filename: str
    file_size: int | None
    mime_type: str | None
    status: str
    duration: float | None
    width: int | None
    height: int | None
    fps: float | None
    video_codec: str | None
    audio_codec: str | None
    thumbnail_path: str | None
    trimmed_file_path: str | None
    analysis_task_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
