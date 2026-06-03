"""
ClipAnalysis ORM model — stores per-clip CV scores and AI metadata.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, JSON, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.clip import Clip


class ClipAnalysis(Base):
    __tablename__ = "clip_analyses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # ── Quality scores (0-10 scale) ───────────────────────────────────────────
    overall_score: Mapped[float | None] = mapped_column(Float)
    blur_score: Mapped[float | None] = mapped_column(Float)       # higher = sharper
    shake_score: Mapped[float | None] = mapped_column(Float)      # higher = more stable
    exposure_score: Mapped[float | None] = mapped_column(Float)   # 10 = perfect exposure
    audio_score: Mapped[float | None] = mapped_column(Float)

    # ── Detected issues ───────────────────────────────────────────────────────
    is_blurry: Mapped[bool] = mapped_column(Boolean, default=False)
    is_shaky: Mapped[bool] = mapped_column(Boolean, default=False)
    is_overexposed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_underexposed: Mapped[bool] = mapped_column(Boolean, default=False)
    has_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_clip_id: Mapped[str | None] = mapped_column(String(36))

    # ── Usable ranges (list of {start, end} dicts) ────────────────────────────
    usable_ranges: Mapped[list | None] = mapped_column(JSON)

    # ── Scene detection ───────────────────────────────────────────────────────
    scene_count: Mapped[int | None] = mapped_column(Integer)
    scenes: Mapped[list | None] = mapped_column(JSON)

    # ── Tags & AI summary ─────────────────────────────────────────────────────
    tags: Mapped[list | None] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text)

    # ── Transcript (Whisper) ──────────────────────────────────────────────────
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_segments: Mapped[list | None] = mapped_column(JSON)

    # ── Perceptual hash (for duplicate detection) ──────────────────────────────
    perceptual_hash: Mapped[str | None] = mapped_column(String(256))

    analysed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_duration_s: Mapped[float | None] = mapped_column(Float)

    clip: Mapped["Clip"] = relationship("Clip", back_populates="analysis")  # noqa: F821
