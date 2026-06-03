"""
LLM-based scoring and tagging.

IMPORTANT DESIGN PRINCIPLE:
  Raw video frames are NEVER sent to the LLM.
  Only structured, pre-computed metadata (scores, durations, transcripts)
  is included in the prompt.

Uses:
  • OpenAI-compatible API (any provider)
  • Returns structured JSON via function calling / response_format
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


# ─── Tag & summarise one clip ─────────────────────────────────────────────────

def tag_and_summarise(clip_metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Given structured metadata, return {tags: [...], summary: str}.
    Falls back to rule-based tagging if LLM is unavailable.
    """
    if not settings.openai_api_key:
        log.warning("no_openai_key_using_rules")
        return _rule_based_tags(clip_metadata)

    try:
        return _llm_tag_and_summarise(clip_metadata)
    except Exception as exc:
        log.warning("llm_tagging_failed", error=str(exc))
        return _rule_based_tags(clip_metadata)


def _llm_tag_and_summarise(metadata: dict[str, Any]) -> dict[str, Any]:
    """Send only structured metadata to the LLM for content understanding."""
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
    )

    # Build a compact, token-efficient prompt
    prompt = _build_prompt(metadata)

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional video editor assistant. "
                    "Analyse the provided clip metadata and return a JSON object with:\n"
                    '  "tags": array of 3-8 lowercase single-word or short-phrase descriptors\n'
                    '  "summary": one sentence describing the clip content and quality\n'
                    "Base your response ONLY on the structured metadata provided. "
                    "Do not hallucinate content."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=256,
        temperature=0.3,
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)

    return {
        "tags": data.get("tags", []),
        "summary": data.get("summary", ""),
    }


def _build_prompt(meta: dict[str, Any]) -> str:
    """Serialise metadata into a compact prompt string."""
    lines = [
        f"Duration: {meta.get('duration', 0):.1f}s",
        f"Resolution: {meta.get('width')}x{meta.get('height')} @ {meta.get('fps', 0):.1f}fps",
        f"Blur score: {meta.get('blur_score', 'N/A')} (0=blurry, 10=sharp)",
        f"Stability score: {meta.get('shake_score', 'N/A')} (0=shaky, 10=stable)",
        f"Exposure score: {meta.get('exposure_score', 'N/A')} (0=poor, 10=perfect)",
        f"Audio codec: {meta.get('audio_codec', 'none')}",
        f"Usable ranges: {len(meta.get('usable_ranges') or [])} segment(s)",
        f"Scene count: {meta.get('scene_count', 1)}",
        f"Motion score: {meta.get('motion_score', 'N/A')}",
    ]
    transcript = (meta.get("transcript") or "").strip()
    if transcript:
        # Truncate long transcripts
        lines.append(f"Transcript excerpt: {transcript[:500]}")

    return "\n".join(lines)


def _rule_based_tags(meta: dict[str, Any]) -> dict[str, Any]:
    """Fallback tagger using CV scores."""
    tags: list[str] = []

    blur = meta.get("blur_score") or 0
    shake = meta.get("shake_score") or 0
    exposure = meta.get("exposure_score") or 0
    motion = meta.get("motion_score") or 0

    if blur >= 7:
        tags.append("sharp")
    elif blur < 3:
        tags.append("blurry")

    if shake >= 7:
        tags.append("stable")
    elif shake < 3:
        tags.append("shaky")

    if exposure >= 7:
        tags.append("well-lit")
    elif meta.get("is_overexposed"):
        tags.append("overexposed")
    elif meta.get("is_underexposed"):
        tags.append("dark")

    if motion > 5:
        tags.append("action")
    else:
        tags.append("static")

    duration = meta.get("duration") or 0
    if duration > 30:
        tags.append("long-clip")
    elif duration < 5:
        tags.append("short-clip")

    summary = (
        f"Clip scored {meta.get('overall_score', 0):.1f}/10. "
        f"{'Good' if (meta.get('overall_score') or 0) >= 6 else 'Poor'} quality footage."
    )

    return {"tags": tags, "summary": summary}


# ─── Timeline sequencing ──────────────────────────────────────────────────────

def suggest_sequence(clips_metadata: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Given a list of scored clip metadata dicts, return a suggested ordering.
    Uses LLM when available; falls back to score-based sort.

    Returns list of {clip_id, order, reason} dicts.
    """
    if not settings.openai_api_key or len(clips_metadata) == 0:
        return _score_based_sequence(clips_metadata)

    try:
        return _llm_sequence(clips_metadata)
    except Exception as exc:
        log.warning("llm_sequence_failed", error=str(exc))
        return _score_based_sequence(clips_metadata)


def _llm_sequence(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
    )

    # Build compact representation — no raw media
    clip_summaries = []
    for c in clips:
        clip_summaries.append(
            {
                "clip_id": c["clip_id"],
                "score": c.get("overall_score"),
                "duration": round(c.get("duration") or 0, 1),
                "tags": c.get("tags", []),
                "summary": (c.get("summary") or "")[:120],
                "scenes": c.get("scene_count", 1),
            }
        )

    prompt = (
        "You are a professional video editor. Given these clips, suggest an optimal rough-cut order.\n"
        "Consider: narrative flow, quality scores, variety, pacing.\n"
        f"Clips (JSON):\n{json.dumps(clip_summaries, indent=2)}\n\n"
        'Return JSON: {"sequence": [{"clip_id": "...", "order": 1, "reason": "..."}, ...]}'
    )

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "You are an expert video editor. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=1024,
        temperature=0.4,
    )

    raw = response.choices[0].message.content or '{"sequence":[]}'
    data = json.loads(raw)
    return data.get("sequence", [])


def _score_based_sequence(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort clips by overall_score descending."""
    sorted_clips = sorted(
        clips,
        key=lambda c: c.get("overall_score") or 0,
        reverse=True,
    )
    return [
        {
            "clip_id": c["clip_id"],
            "order": i + 1,
            "reason": f"Sorted by quality score ({c.get('overall_score', 0):.1f})",
        }
        for i, c in enumerate(sorted_clips)
    ]
