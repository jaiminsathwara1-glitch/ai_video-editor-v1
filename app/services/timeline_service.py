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
    analysis_mode: str = "gemini",
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
    # DESIGN: Include ALL footage that covers the 7-step sequence.
    # The only hard exclusion is exact duplicate clips (perceptual hash match).
    #
    # We NO LONGER hard-exclude based on score threshold or empty usable_ranges:
    #   • Low-score clips: still included — the sequencer places them last within
    #     their step and the user can reject them manually in the UI.
    #   • Empty usable_ranges: fall back to the full clip duration.  CV analysis
    #     may be too strict (e.g. handheld walk-through with no perfectly stable
    #     window still contains valid property footage).
    eligible: list[dict[str, Any]] = []
    skipped_dup       = 0
    below_score_count = 0
    fallback_ranges   = 0

    for clip, analysis in rows:
        score = analysis.overall_score or 0.0

        if analysis.has_duplicate:
            skipped_dup += 1
            log.debug(
                "timeline_skip_duplicate",
                clip_id=clip.id,
                filename=clip.original_filename or "",
            )
            continue

        # Soft quality note — log it but do NOT exclude
        if score < min_score:
            below_score_count += 1
            log.info(
                "timeline_below_score_included",
                clip_id=clip.id,
                score=round(score, 2),
                min_score=min_score,
                filename=clip.original_filename or "",
            )

        # Resolve usable ranges — fall back to full clip if CV found none
        usable = analysis.usable_ranges or []
        if not usable:
            clip_dur = clip.duration or 0.0
            if clip_dur >= 0.5:          # at least half a second of footage
                usable = [{"start": 0.0, "end": round(clip_dur, 3)}]
                fallback_ranges += 1
                log.info(
                    "timeline_fallback_full_clip",
                    clip_id=clip.id,
                    duration=round(clip_dur, 2),
                    score=round(score, 2),
                    filename=clip.original_filename or "",
                    reason="no_usable_ranges_cv_too_strict_using_full_clip",
                )
            else:
                log.info(
                    "timeline_skip_zero_duration",
                    clip_id=clip.id,
                    duration=clip_dur,
                )
                continue   # truly no footage to use

        meta = _clip_to_meta(clip, analysis)
        meta["usable_ranges"] = usable   # override with resolved ranges
        eligible.append(meta)

    log.info(
        "timeline_filter_summary",
        total=len(rows),
        eligible=len(eligible),
        skipped_duplicates=skipped_dup,
        below_score_threshold=below_score_count,
        used_fallback_full_clip=fallback_ranges,
        min_score=min_score,
        project_id=project_id,
    )



    if not eligible:
        raise ValueError(
            f"No clips are available for the timeline. "
            f"Tried {len(rows)} clips — {skipped_dup} were exact duplicates and excluded. "
            "All remaining clips had zero duration. Try re-analysing your clips."
        )


    log.info("timeline_eligible_clips", count=len(eligible), project_id=project_id)

    # ── 3. AI sequencing ──────────────────────────────────────────────────────
    sequence = suggest_sequence(eligible, analysis_mode=analysis_mode)   # [{clip_id, order, reason}, ...]
    clip_meta_by_id = {c["clip_id"]: c for c in eligible}

    log.info(
        "timeline_sequence_result",
        analysis_mode=analysis_mode,
        sequence=[(s["clip_id"][:8], s.get("order"), s.get("reason", "")[:40]) for s in sequence],
    )

    # ── 4. Build timeline entries ──────────────────────────────────────────────────────
    #
    # Two design decisions applied here:
    #
    # A) BEST RANGE ONLY: When a clip has multiple usable segments we pick only
    #    the LONGEST one.  Including all segments bloats the timeline with
    #    repetitive footage of the same room.
    #
    # B) PROPORTIONAL STEP BUDGETING: When target_duration is set the old code
    #    just stopped when total_dur >= target, which meant every step after
    #    the first 1–2 was completely absent.  Now we distribute the budget
    #    proportionally across all 7 steps so every step is represented and
    #    clips are trimmed at the cut-point to fit their step budget exactly.

    from collections import defaultdict
    from app.ai.llm_scorer import _classify_to_step

    def _best_range(usable: list) -> dict | None:
        """Return the single longest usable range for a clip."""
        if not usable:
            return None
        return max(usable, key=lambda r: r["end"] - r["start"])

    def _make_entry(clip_id: str, rng: dict, score, reason: str, order: int) -> dict:
        return {
            "clip_id":   clip_id,
            "order":     order,
            "in_point":  round(rng["start"], 3),
            "out_point": round(rng["end"],   3),
            "track":     0,
            "score":     score,
            "reason":    reason,
        }

    entries: list[dict[str, Any]] = []
    total_dur    = 0.0
    global_order = 1

    sorted_seq = sorted(sequence, key=lambda s: s.get("order", 0))

    def _classify_to_sub_step(meta: dict[str, Any], step: int) -> str:
        """
        Sub-classify a clip to group by unique rooms/areas so we only select the best
        shot for each distinct space.
        """
        tags     = " ".join(t.lower() for t in (meta.get("tags") or []))
        summary  = (meta.get("summary") or "").lower()
        filename = (meta.get("filename") or "").lower()
        combined = f"{tags} {summary} {filename}"

        if step == 1:
            return "exterior"
        elif step == 2:
            return "entrance"
        elif step == 3:
            if any(k in combined for k in ["kitch", "cook", "island", "cabinet", "stove"]):
                return "kitchen"
            elif any(k in combined for k in ["din", "table"]):
                return "dining"
            else:
                return "living_room"
        elif step == 4:
            if any(k in combined for k in ["master", "bed 1", "bedroom 1"]):
                return "master_bedroom"
            elif any(k in combined for k in ["guest", "bed 2", "bedroom 2"]):
                return "guest_bedroom"
            else:
                return "bedroom_other"
        elif step == 5:
            if any(k in combined for k in ["master bath", "ensuite", "en-suite", "bath 1"]):
                return "master_bathroom"
            else:
                return "bathroom_other"
        elif step == 6:
            if any(k in combined for k in ["pool", "swim"]):
                return "pool"
            elif any(k in combined for k in ["patio", "deck", "terrace", "alfresco", "pergola", "bbq"]):
                return "patio_deck"
            else:
                return "backyard_garden"
        elif step == 7:
            return "outro"
        return "unclassified"

    # Group clips by their distinct sub-step (room type)
    sub_step_clips = defaultdict(list)
    for seq_item in sorted_seq:
        clip_id = seq_item["clip_id"]
        meta    = clip_meta_by_id.get(clip_id)
        if not meta:
            continue
        step = seq_item.get("step") or _classify_to_step(meta)
        if step < 1 or step > 7:
            continue   # Exclude step 8 (unclassified)
        sub_step = _classify_to_sub_step(meta, step)
        sub_step_clips[sub_step].append((seq_item, meta, step))

    # Pick the single highest-scoring clip for each unique room / sub-step
    filtered_seq: list[dict[str, Any]] = []
    # Loop in step order to preserve Step 1 -> Step 7 structure
    for step in range(1, 8):
        # Find all sub-steps belonging to this major step
        step_sub_steps = [
            ss for ss in sub_step_clips.keys()
            if (ss == "exterior" and step == 1) or
               (ss == "entrance" and step == 2) or
               (ss in ["kitchen", "dining", "living_room"] and step == 3) or
               (ss in ["master_bedroom", "guest_bedroom", "bedroom_other"] and step == 4) or
               (ss in ["master_bathroom", "bathroom_other"] and step == 5) or
               (ss in ["pool", "patio_deck", "backyard_garden"] and step == 6) or
               (ss == "outro" and step == 7)
        ]
        for sub_step in step_sub_steps:
            clips_in_sub_step = sub_step_clips[sub_step]
            if not clips_in_sub_step:
                continue
            # Pick the best clip in this room by overall quality score
            best_item = max(clips_in_sub_step, key=lambda x: x[1].get("overall_score") or 0.0)
            item = best_item[0]
            item["step"] = best_item[2]   # Ensure major step is correct
            filtered_seq.append(item)

    log.info(
        "timeline_one_clip_per_room_filter",
        original_count=len(sorted_seq),
        filtered_count=len(filtered_seq),
        included_rooms=[(item["clip_id"][:8], item["step"]) for item in filtered_seq],
    )


    if not target_duration:
        # ── PATH A: No cap — best range per clip, full sequence order ──────────
        for seq_item in filtered_seq:
            clip_id = seq_item["clip_id"]
            meta    = clip_meta_by_id.get(clip_id)
            if not meta:
                continue
            best = _best_range(meta.get("usable_ranges") or [])
            if not best:
                continue
            seg_dur = best["end"] - best["start"]
            if seg_dur < 0.3:
                continue
            entries.append(_make_entry(clip_id, best, meta.get("overall_score"),
                                       seq_item.get("reason", ""), global_order))
            global_order += 1
            total_dur    += seg_dur

    else:
        # ── PATH B: Target duration — proportional step budgeting ───────────

        # 1. Group sequence items by their 7-step category
        steps_items: dict[int, list] = defaultdict(list)
        for seq_item in filtered_seq:
            clip_id = seq_item["clip_id"]
            meta    = clip_meta_by_id.get(clip_id)
            if not meta:
                continue
            step = seq_item["step"]
            best = _best_range(meta.get("usable_ranges") or [])
            if not best:
                continue
            seg_dur = best["end"] - best["start"]
            if seg_dur < 0.3:
                continue
            steps_items[step].append((seq_item, meta, best, seg_dur))

        # 2. Natural (uncapped) duration per step
        step_natural: dict[int, float] = {
            step: sum(sd for _, _, _, sd in items)
            for step, items in steps_items.items()
        }
        total_natural = sum(step_natural.values()) or 1.0

        # 3. Guarantee each present step gets MIN_STEP_SECS,
        #    then distribute remaining budget proportionally.
        MIN_STEP_SECS   = 5.0
        present_steps   = sorted(steps_items.keys())
        guaranteed      = {s: min(MIN_STEP_SECS, step_natural[s]) for s in present_steps}
        guaranteed_total= sum(guaranteed.values())
        flex_budget     = max(0.0, target_duration - guaranteed_total)
        flex_natural    = sum(
            max(0.0, step_natural[s] - guaranteed[s]) for s in present_steps
        )

        step_budget: dict[int, float] = {}
        for s in present_steps:
            flex_share = (
                (max(0.0, step_natural[s] - guaranteed[s]) / flex_natural * flex_budget)
                if flex_natural > 0 else 0.0
            )
            step_budget[s] = guaranteed[s] + flex_share

        log.info(
            "timeline_step_budgets",
            target=target_duration,
            total_natural=round(total_natural, 1),
            budgets={s: round(b, 1) for s, b in step_budget.items()},
        )

        # 4. Fill entries step by step within each step's budget
        for step in present_steps:
            budget    = step_budget.get(step, 0.0)
            step_used = 0.0

            for seq_item, meta, best, seg_dur in steps_items[step]:
                if step_used >= budget:
                    break
                clip_id   = seq_item["clip_id"]
                available = budget - step_used

                if seg_dur <= available:
                    # Whole best range fits inside the step's budget
                    entries.append(_make_entry(
                        clip_id, best, meta.get("overall_score"),
                        seq_item.get("reason", ""), global_order
                    ))
                    global_order += 1
                    step_used    += seg_dur
                    total_dur    += seg_dur
                elif available >= 1.0:
                    # Trim out-point to fill the remaining step budget exactly
                    trimmed = {"start": best["start"],
                               "end":   best["start"] + available}
                    entries.append(_make_entry(
                        clip_id, trimmed, meta.get("overall_score"),
                        seq_item.get("reason", "")
                        + f" [trimmed {available:.1f}s of {seg_dur:.1f}s]",
                        global_order
                    ))
                    global_order += 1
                    step_used    += available
                    total_dur    += available
                # < 1 second of budget left — not worth a micro-segment

    # Guarantee ascending order before persisting.
    entries.sort(key=lambda e: e["order"])

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
            f"{below_score_count} below score threshold (still included). "
            f"{fallback_ranges} used full-clip fallback (CV found no usable ranges)."
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
        "filename": clip.original_filename or "",   # ← key for room classification
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
