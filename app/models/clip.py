"""
Clip ORM model — represents one uploaded video file.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, BigInteger
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.analysis import ClipAnalysis


class ClipStatus(str):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    ANALYSING = "analysing"
    ANALYSED = "analysed"
    ERROR = "error"


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="uploading", nullable=False)

    # ── FFprobe metadata ──────────────────────────────────────────────────────
    duration: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    video_codec: Mapped[str | None] = mapped_column(String(64))
    audio_codec: Mapped[str | None] = mapped_column(String(64))
    bit_rate: Mapped[int | None] = mapped_column(BigInteger)
    nb_frames: Mapped[int | None] = mapped_column(Integer)
    raw_metadata: Mapped[dict | None] = mapped_column(JSON)

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024))
    trimmed_file_path: Mapped[str | None] = mapped_column(String(1024))

    # ── Celery task tracking ──────────────────────────────────────────────────
    analysis_task_id: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project: Mapped["Project"] = relationship("Project", back_populates="clips")  # noqa: F821
    chunks: Mapped[list["ClipChunk"]] = relationship(
        "ClipChunk", back_populates="clip", cascade="all, delete-orphan"
    )
    analysis: Mapped["ClipAnalysis | None"] = relationship(  # noqa: F821
        "ClipAnalysis", back_populates="clip", uselist=False, cascade="all, delete-orphan"
    )


class ClipChunk(Base):
    """Tracks received chunks for resumable uploads."""

    __tablename__ = "clip_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    clip: Mapped["Clip"] = relationship("Clip", back_populates="chunks")
