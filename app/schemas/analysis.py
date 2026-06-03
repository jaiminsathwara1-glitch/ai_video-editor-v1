from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class UsableRange(BaseModel):
    start: float
    end: float
    reason: str | None = None


class SceneInfo(BaseModel):
    scene_number: int
    start_time: float
    end_time: float
    duration: float


class AnalysisRead(BaseModel):
    id: str
    clip_id: str

    overall_score: float | None
    blur_score: float | None
    shake_score: float | None
    exposure_score: float | None
    audio_score: float | None

    is_blurry: bool
    is_shaky: bool
    is_overexposed: bool
    is_underexposed: bool
    has_duplicate: bool
    duplicate_of_clip_id: str | None

    usable_ranges: list[UsableRange] | None
    scene_count: int | None
    scenes: list[SceneInfo] | None

    tags: list[str] | None
    summary: str | None
    transcript: str | None

    analysed_at: datetime | None
    analysis_duration_s: float | None

    model_config = {"from_attributes": True}
