"""
Project ORM model — groups a batch of uploaded clips.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.timeline import Timeline


class ProjectStatus(str):
    CREATED = "created"
    ANALYSING = "analysing"
    READY = "ready"
    ERROR = "error"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(
        String(32), default="created", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    clips: Mapped[list["Clip"]] = relationship(  # noqa: F821
        "Clip", back_populates="project", cascade="all, delete-orphan"
    )
    timelines: Mapped[list["Timeline"]] = relationship(  # noqa: F821
        "Timeline", back_populates="project", cascade="all, delete-orphan"
    )
