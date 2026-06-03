"""
Timeline ORM model — stores generated rough-cut timeline data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING

from sqlalchemy import String, Float, DateTime, ForeignKey, JSON, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class Timeline(Base):
    __tablename__ = "timelines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), default="Rough Cut", nullable=False)

    # ── Ordered clip entries ──────────────────────────────────────────────────
    # [{clip_id, in_point, out_point, track, order, score, reason}, ...]
    entries: Mapped[list | None] = mapped_column(JSON)

    total_duration: Mapped[float | None] = mapped_column(Float)
    clip_count: Mapped[int | None] = mapped_column(Integer)

    # ── Export paths ──────────────────────────────────────────────────────────
    xml_export_path: Mapped[str | None] = mapped_column(String(1024))
    edl_export_path: Mapped[str | None] = mapped_column(String(1024))
    otio_export_path: Mapped[str | None] = mapped_column(String(1024))
    render_video_path: Mapped[str | None] = mapped_column(String(1024))

    generation_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    project: Mapped["Project"] = relationship("Project", back_populates="timelines")  # noqa: F821
