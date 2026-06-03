"""
Timeline generation service.

Algorithm:
  1. Filter clips by min quality score (configurable)
  2. Exclude duplicates (keep original)
  3. Call LLM sequence suggester with structured metadata
  4. Trim to usable ranges
  5. Optionally cap total duration
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.clip import Clip
from app.models.analysis import ClipAnalysis
from app.models.timeline import Timeline
from app.ai.llm_scorer import suggest_sequence

log = structlog.get_logger(__name__)
settings = get_settings()


async def generate_timeline(
    db: AsyncSession,
    project_id: str,
    name: str = "Rough Cut",
    min_score: float = 0.0,    # slider-controlled; 0 = include all clips with usable ranges
    target_duration: float | None = None,
) -> Timeline:
    """
    Generate a rough-cut timeline for a project.
    Returns a persisted Timeline ORM object.
    """

    # ── 1. Load analysed clips ────────────────────────────────────────────────
    result = await db.execute(
        select(Clip, ClipAnalysis)
        .join(ClipAnalysis, ClipAnalysis.clip_id == Clip.id)
        .where(
            Clip.project_id == project_id,
            Clip.status == "analysed",
        )
    )
    rows = result.all()

    if not rows:
        raise ValueError("No analysed clips found for project. Run analysis first.")

    # ── 2. Filter by quality & deduplicate ────────────────────────────────────
    # NOTE: We intentionally do NOT hard-reject clips based on is_blurry /
    # is_shaky flags alone.  Those flags feed into overall_score already
    # (blur 40%, shake 35% of the weighted formula), so the score threshold
    # below is the single quality gate.  A hard flag-based exclude was
    # removing too many clips that only had brief bad moments but were
    # otherwise usable (usable_ranges trims those bad parts out anyway).
    eligible: list[dict[str, Any]] = []
    skipped_dup        = 0
    skipped_score      = 0
    skipped_no_ranges  = 0
    for clip, analysis in rows:
        score = analysis.overall_score or 0.0
        if analysis.has_duplicate:
            skipped_dup += 1
            continue
        if score < min_score:
            skipped_score += 1
            continue
        # Skip clips that have no usable ranges (all blurry/shaky)
        usable = analysis.usable_ranges or []
        if not usable:
            skipped_no_ranges += 1
            log.info(
                "timeline_skip_no_usable_ranges",
                clip_id=clip.id,
                score=round(score, 2),
            )
            continue
        eligible.append(_clip_to_meta(clip, analysis))

    log.info(
        "timeline_filter_summary",
        total=len(rows),
        eligible=len(eligible),
        skipped_duplicates=skipped_dup,
        skipped_low_score=skipped_score,
        skipped_no_usable_ranges=skipped_no_ranges,
        min_score=min_score,
        project_id=project_id,
    )

    if not eligible:
        raise ValueError(
            f"No clips have usable (non-blurry, non-shaky) segments. "
            f"Tried {len(rows)} clips — {skipped_dup} duplicates, "
            f"{skipped_score} below score {min_score:.1f}, "
            f"{skipped_no_ranges} had no stable frames after analysis. "
            "Try lowering the Min Score slider or re-analysing your clips."
        )

    log.info("timeline_eligible_clips", count=len(eligible), project_id=project_id)

    # ── 3. AI sequencing ──────────────────────────────────────────────────────
    sequence = suggest_sequence(eligible)   # [{clip_id, order, reason}, ...]
    clip_meta_by_id = {c["clip_id"]: c for c in eligible}

    # ── 4. Build timeline entries with trim points ────────────────────────────
    entries: list[dict[str, Any]] = []
    total_dur = 0.0

    for seq_item in sorted(sequence, key=lambda s: s.get("order", 0)):
        clip_id = seq_item["clip_id"]
        meta = clip_meta_by_id.get(clip_id)
        if not meta:
            continue

        clip_duration = meta.get("duration") or 0.0
        usable = meta.get("usable_ranges") or []

        # usable_ranges is guaranteed non-empty here (empty clips were skipped above)
        for rng in usable:
            seg_dur = rng["end"] - rng["start"]
            if seg_dur < 0.3:
                continue

            entries.append(
                {
                    "clip_id": clip_id,
                    "order": len(entries) + 1,
                    "in_point": rng["start"],
                    "out_point": rng["end"],
                    "track": 0,
                    "score": meta.get("overall_score"),
                    "reason": seq_item.get("reason", ""),
                }
            )
            total_dur += seg_dur

            if target_duration and total_dur >= target_duration:
                break

        if target_duration and total_dur >= target_duration:
            break

    # ── 5. Persist ────────────────────────────────────────────────────────────
    timeline = Timeline(
        project_id=project_id,
        name=name,
        entries=entries,
        total_duration=round(total_dur, 3),
        clip_count=len({e["clip_id"] for e in entries}),
        generation_notes=(
            f"Generated from {len(eligible)} eligible clips (min score ≥ {min_score}). "
            f"{skipped_dup} duplicates excluded. "
            f"{skipped_score} below score threshold. "
            f"{skipped_no_ranges} had no stable frames (all blurry/shaky)."
        ),
    )
    db.add(timeline)
    await db.flush()

    log.info(
        "timeline_generated",
        timeline_id=timeline.id,
        entries=len(entries),
        total_dur=total_dur,
    )
    return timeline


def _clip_to_meta(clip: Clip, analysis: ClipAnalysis) -> dict[str, Any]:
    return {
        "clip_id": clip.id,
        "file_path": clip.file_path,
        "duration": clip.duration,
        "fps": clip.fps,
        "width": clip.width,
        "height": clip.height,
        "overall_score": analysis.overall_score,
        "blur_score": analysis.blur_score,
        "shake_score": analysis.shake_score,
        "exposure_score": analysis.exposure_score,
        "is_blurry": analysis.is_blurry,
        "is_shaky": analysis.is_shaky,
        "usable_ranges": analysis.usable_ranges or [],
        "tags": analysis.tags or [],
        "summary": analysis.summary or "",
        "scene_count": analysis.scene_count,
        "transcript": analysis.transcript or "",
    }
