from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class TimelineEntry(BaseModel):
    clip_id: str
    order: int
    in_point: float       # seconds
    out_point: float      # seconds
    track: int = 0
    score: float | None = None
    reason: str | None = None


class TimelineCreate(BaseModel):
    project_id: str
    name: str = "Rough Cut"
    min_score: float = Field(default=0.0, ge=0, le=10)   # 0 = include all stable clips
    target_duration: float | None = None  # seconds; None = use all good clips


class TimelineRead(BaseModel):
    id: str
    project_id: str
    name: str
    entries: list[TimelineEntry] | None
    total_duration: float | None
    clip_count: int | None
    xml_export_path: str | None
    edl_export_path: str | None
    otio_export_path: str | None
    render_video_path: str | None
    generation_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
