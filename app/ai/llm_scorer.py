"""
LLM-based scoring, tagging, and visual analysis.

DESIGN PRINCIPLE:
  To support semantic visual search, keyframe thumbnails (pre-extracted & resized)
  are encoded as base64 and sent to a vision-capable LLM (such as Gemini 3.5 Flash)
  along with structured metadata (quality scores, duration, transcripts).
  This allows the AI to describe the visual context of the video (e.g. recognizing a car, wedding, beach)
  even if the clip has no dialogue/transcript.

Uses:
  • OpenAI-compatible API (any provider, prefers Gemini for Multimodal Vision)
  • Returns structured JSON via response_format
"""
from __future__ import annotations

import json
import base64
from pathlib import Path
from typing import Any

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


# ─── Tag & summarise one clip ─────────────────────────────────────────────────

def tag_and_summarise(clip_metadata: dict[str, Any], analysis_mode: str = "gemini") -> dict[str, Any]:
    """
    Given structured metadata and visual keyframes, return {tags: [...], summary: str}.
    Falls back to rule-based tagging if no LLM API keys are configured or analysis_mode is rule_based.
    """
    if analysis_mode == "rule_based":
        log.info("user_forced_rule_based_tagging")
        return _rule_based_tags(clip_metadata)

    if not settings.openai_api_key and not settings.gemini_api_key and not getattr(settings, "groq_api_key", ""):
        log.warning("no_llm_api_key_configured_using_rules")
        return _rule_based_tags(clip_metadata)

    try:
        return _llm_tag_and_summarise(clip_metadata, analysis_mode)
    except Exception as exc:
        log.error(
            "llm_tagging_failed_falling_back_to_rules",
            analysis_mode=analysis_mode,
            error=str(exc),
            clip_id=clip_metadata.get("clip_id", "unknown"),
            exc_info=True,
        )
        return _rule_based_tags(clip_metadata)


def _llm_tag_and_summarise(metadata: dict[str, Any], analysis_mode: str = "gemini") -> dict[str, Any]:
    """Send structured metadata and base64 keyframe images to the Vision LLM for visual understanding."""
    from openai import OpenAI

    use_vision = analysis_mode in ["gemini", "groq_vision"]

    # Prefer Gemini for Multimodal Vision analysis if configured
    if analysis_mode == "gemini" and settings.gemini_api_key:
        client = OpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url or None,
        )
        model = settings.gemini_model or "gemini-3.5-flash"
        log.info("using_gemini_vision", model=model)
    elif analysis_mode == "groq_vision" and getattr(settings, "groq_api_key", ""):
        # "Groq (Vision)" — local Ollama / qwen with keyframe images
        client = OpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url or None,
        )
        model = settings.groq_model or "llama-3.2-11b-vision-preview"
        log.info("using_groq_vision", model=model)
    elif analysis_mode == "groq" and (getattr(settings, "groq_text_api_key", "") or getattr(settings, "groq_api_key", "")):
        # "Groq / OpenAI (Text)" — dedicated text credentials (real Groq API)
        text_api_key  = getattr(settings, "groq_text_api_key", "") or settings.groq_api_key
        text_base_url = getattr(settings, "groq_text_base_url", "") or settings.groq_base_url or None
        text_model    = getattr(settings, "groq_text_model", "") or "llama-3.3-70b-versatile"
        client = OpenAI(api_key=text_api_key, base_url=text_base_url)
        model  = text_model
        log.info("using_groq_text", model=model, base_url=text_base_url)
    else:
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        model = settings.openai_model
        log.info("using_openai_llm", model=model)

    # Load and encode keyframe thumbnails if present
    clip_id = metadata.get("clip_id")
    project_id = metadata.get("project_id")
    base64_imgs = []

    if use_vision and clip_id and project_id:
        thumb_dir = Path(settings.thumbnail_dir) / project_id
        if thumb_dir.exists():
            thumb_files = sorted(thumb_dir.glob(f"{clip_id}_thumb_*.jpg"))
            # qwen2.5vl:3b has a 4096-token context window.
            # Each base64 image costs ~1000-1100 tokens; the text prompt + system
            # prompt uses ~500 tokens. Sending 5 images (5500+ tokens) overflows
            # the context and causes a 400 BadRequestError → rule-based fallback.
            # Limit: 1 image for groq_vision (small local model), all for gemini.
            max_imgs = 1 if analysis_mode == "groq_vision" else len(thumb_files)
            for tf in thumb_files[:max_imgs]:
                try:
                    with open(tf, "rb") as image_file:
                        encoded = base64.b64encode(image_file.read()).decode("utf-8")
                        base64_imgs.append(encoded)
                except Exception as exc:
                    log.warning("failed_to_encode_thumbnail", path=str(tf), error=str(exc))

    prompt = _build_prompt(metadata)

    # Formulate multimodal or text-only prompt content
    user_content = []
    if base64_imgs:
        user_content.append({
            "type": "text",
            "text": (
                "You are analyzing a sequence of keyframes extracted from a single video clip.\n"
                "Review these keyframe images visually to understand the core subject, action, setting, "
                "and context of the video. Then combine your visual analysis with the metadata below:\n\n"
                f"{prompt}"
            )
        })
        for img in base64_imgs:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img}"
                }
            })
        log.info("sending_multimodal_request", keyframe_count=len(base64_imgs))
    else:
        user_content.append({
            "type": "text",
            "text": prompt
        })
        log.info("sending_text_only_request")

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a video editor assistant. "
                    "Respond ONLY with a valid JSON object with exactly two keys: "
                    "'tags' (array of 3-8 lowercase descriptors) and "
                    "'summary' (one sentence). "
                    "No markdown, no backticks. Start with '{' and end with '}'."
                ),
            },
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
    }
    # JSON mode flags:
    #   gemini       — uses its own native format, does NOT use response_format
    #   groq_vision  — Ollama/qwen2.5vl does NOT reliably support response_format
    #                  when images are included in the request (multimodal). Sending
    #                  it causes silent failures → plain text → JSON parse error →
    #                  rule-based fallback. We rely on the strong system prompt instead.
    #   groq         — real Groq cloud (Llama-4-Scout) supports json_object ✅
    #   openai/else  — standard OpenAI supports json_object ✅
    if analysis_mode not in ("gemini", "groq_vision"):
        kwargs["response_format"] = {"type": "json_object"}
    if analysis_mode == "groq_vision":
        # Ask Ollama to extend its context window beyond the default 4096 so
        # even with 1 image + prompt we have headroom for the JSON response.
        kwargs["extra_body"] = {"options": {"num_ctx": 8192}}
        kwargs["max_tokens"] = 512   # JSON output only needs ~100-200 tokens
    elif analysis_mode != "gemini":
        kwargs["max_tokens"] = 512

    response = client.chat.completions.create(**kwargs)

    raw = response.choices[0].message.content or "{}"
    log.info("raw_llm_response", raw=raw, response=str(response))
    
    # Strip markdown block formatting if present
    cleaned_raw = raw.strip()
    if cleaned_raw.startswith("```"):
        lines = cleaned_raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned_raw = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned_raw)
    except Exception as exc:
        log.error("json_parse_failed", raw_response=raw, err=str(exc))
        raise exc

    return {
        "tags": data.get("tags", []),
        "summary": data.get("summary", ""),
    }


def _build_prompt(meta: dict[str, Any]) -> str:
    """Serialise metadata into a compact prompt string."""
    lines = [
        f"Filename: {meta.get('filename', 'unknown')}",
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

    # Real Estate Sequencing Heuristic based on filename
    filename = (meta.get("filename") or "").lower()
    
    # 1. Intro / Exterior
    if any(k in filename for k in ["ext", "drone", "front", "facade", "street"]):
        tags.append("intro_exterior")
    # 2. Grand Entrance
    elif any(k in filename for k in ["entran", "door", "foyer", "hallway"]):
        tags.append("entrance")
    # 3. Main Living Area
    elif any(k in filename for k in ["liv", "kitch", "din", "lounge"]):
        tags.append("main_living")
    # 4. Private Quarters
    elif any(k in filename for k in ["bed", "master", "guest"]):
        tags.append("private_quarters")
    # 5. Bathroom / Toilet
    elif any(k in filename for k in ["bath", "toilet", "wash", "ensuite"]):
        tags.append("bathroom")
    # 6. Outdoor Living Space
    elif any(k in filename for k in ["pool", "backyard", "patio", "deck", "garden"]):
        tags.append("outdoor_living")
    # 7. Outro
    elif any(k in filename for k in ["out", "close", "end", "sunset"]):
        tags.append("outro")
    else:
        # Fallback heuristic
        if exposure >= 6 and motion > 4:
            tags.append("intro_exterior")
        elif exposure < 5:
            tags.append("main_living")
        else:
            tags.append("private_quarters")

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

def suggest_sequence(clips_metadata: list[dict[str, Any]], analysis_mode: str = "gemini") -> list[dict[str, Any]]:
    """
    Given a list of scored clip metadata dicts, return a suggested ordering.
    Uses LLM when available; falls back to score-based sort.

    Returns list of {clip_id, order, step, reason} dicts.
    """
    if analysis_mode == "rule_based" or (not settings.openai_api_key and not settings.gemini_api_key and not getattr(settings, "groq_api_key", "")) or len(clips_metadata) == 0:
        return _score_based_sequence(clips_metadata)

    try:
        raw_sequence = _llm_sequence(clips_metadata, analysis_mode)
        return _enforce_strict_7_step_sequence(raw_sequence, clips_metadata)
    except Exception as exc:
        log.warning("llm_sequence_failed_falling_back", error=str(exc))
        return _score_based_sequence(clips_metadata)


def _enforce_strict_7_step_sequence(sequence: list[dict[str, Any]], clips_metadata: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Ensures that no matter what order or steps an LLM model returned, the sequence
    is strictly sorted by step order (1 to 7), preserving the LLM's relative
    ordering within each step.
    """
    meta_by_id = {c["clip_id"]: c for c in clips_metadata}
    classified_items = []

    for item in sequence:
        clip_id = item["clip_id"]
        meta = meta_by_id.get(clip_id, {})

        # Determine step number (1-8)
        step = item.get("step")
        if not isinstance(step, int) or step < 1 or step > 8:
            step = _classify_to_step(meta)

        classified_items.append({
            "clip_id": clip_id,
            "original_order": item.get("order", 999),
            "step": step,
            "reason": item.get("reason", ""),
        })

    # Sort primarily by step (1 to 8), and secondarily by the LLM's preferred relative order
    classified_items.sort(key=lambda x: (x["step"], x["original_order"]))

    # Re-assign sequential orders starting from 1
    final_sequence = []
    for idx, item in enumerate(classified_items):
        final_sequence.append({
            "clip_id": item["clip_id"],
            "order": idx + 1,
            "step": item["step"],
            "reason": item["reason"] or f"Step {item['step']}",
        })

    log.info(
        "enforced_7_step_sequence",
        total_clips=len(final_sequence),
        steps_summary=[(f"{item['clip_id'][:6]}...", item["step"]) for item in final_sequence]
    )
    return final_sequence



def _llm_sequence(clips: list[dict[str, Any]], analysis_mode: str = "gemini") -> list[dict[str, Any]]:
    from openai import OpenAI

    # ── Route to correct API client ────────────────────────────────────────────
    if analysis_mode == "gemini" and settings.gemini_api_key:
        client = OpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url or None,
        )
        model = settings.gemini_model or "gemini-3.5-flash"
        log.info("sequence_using_gemini", model=model)
    elif analysis_mode in ("groq_vision", "groq") and getattr(settings, "groq_api_key", ""):
        if analysis_mode == "groq":
            # "Groq / OpenAI (Text)" — use dedicated text credentials if set,
            # otherwise fall back to the vision credentials.
            text_api_key  = getattr(settings, "groq_text_api_key", "") or settings.groq_api_key
            text_base_url = getattr(settings, "groq_text_base_url", "") or settings.groq_base_url or None
            text_model    = getattr(settings, "groq_text_model", "") or "llama-3.3-70b-versatile"
            client = OpenAI(api_key=text_api_key, base_url=text_base_url)
            model  = text_model
            log.info("sequence_using_groq_text", model=model, base_url=text_base_url)
        else:
            # "Groq (Vision)" — use the vision credentials (e.g. Ollama / groq_model)
            client = OpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url or None,
            )
            model = settings.groq_model or "llama-3.2-11b-vision-preview"
            log.info("sequence_using_groq_vision", model=model)
    else:
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        model = settings.openai_model
        log.info("sequence_using_openai", model=model)

    # ── Build compact clip representations for the prompt ─────────────────────
    # IMPORTANT: include filename — it is the single most reliable signal for
    # room classification when clips have generic camera names like LREP0121.MP4
    # and the vision LLM summary may only say "interior room with good lighting".
    clip_summaries = []
    for c in clips:
        # Pre-classify using our local keyword classifier so the LLM has an
        # explicit hint even when tags/summaries are vague.
        step_hint = _classify_to_step(c)
        clip_summaries.append(
            {
                "clip_id": c["clip_id"],
                "filename": (c.get("filename") or ""),          # key for room context
                "score": c.get("overall_score"),
                "duration": round(c.get("duration") or 0, 1),
                "tags": c.get("tags", []),
                "summary": (c.get("summary") or "")[:150],
                "scenes": c.get("scene_count", 1),
                "suggested_step": step_hint,                    # local pre-classification
            }
        )

    prompt = (
        "You are a professional real estate video editor.\n"
        "Order the clips below into a smooth real estate showcase following this STRICT 7-step flow:\n"
        "  Step 1 — Exterior / Drone / Street (first impression)\n"
        "  Step 2 — Grand Entrance / Foyer / Front Door\n"
        "  Step 3 — Main Living Area: Living Room, Kitchen, Dining Room\n"
        "  Step 4 — Private Quarters: Bedrooms (master first, then guest)\n"
        "  Step 5 — Bathrooms / Ensuite\n"
        "  Step 6 — Outdoor Living: Backyard, Pool, Patio, Garden\n"
        "  Step 7 — Outro / Closing Shot (e.g., sunset, aerial retreat)\n\n"
        "RULES:\n"
        "• The 'suggested_step' field in each clip is a local hint — use it as strong guidance.\n"
        "• Use the filename, tags, AND summary together to decide which step a clip belongs to.\n"
        "• Include ALL clips in your output, even if step is uncertain — place uncertain clips\n"
        "  near the most likely step based on visual context.\n"
        "• Multiple clips per step are allowed and expected.\n"
        "• 'order' MUST be a unique integer starting at 1, incrementing by 1 for every clip.\n"
        "• DO NOT skip clips. Every clip_id in the input must appear exactly once in the output.\n\n"
        f"Clips:\n{json.dumps(clip_summaries, indent=2)}\n\n"
        'Return ONLY valid JSON: {"sequence": [{"clip_id": "...", "order": 1, "step": 1, "reason": "..."}, ...]}'
    )

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert real estate video editor. "
                    "You MUST return only valid JSON with a 'sequence' array. "
                    "Every clip_id from the input must appear exactly once in the output."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,   # lower temp = more deterministic ordering
    }

    # JSON mode: Gemini uses its own format; all others (Ollama/qwen, Groq, OpenAI) support json_object
    if analysis_mode != "gemini":
        kwargs["response_format"] = {"type": "json_object"}
    if analysis_mode != "gemini":
        kwargs["max_tokens"] = 2048   # enough for 20+ clip sequence JSON

    response = client.chat.completions.create(**kwargs)

    raw = response.choices[0].message.content or '{"sequence":[]}'
    log.info("llm_sequence_raw_response", length=len(raw), preview=raw[:200])

    cleaned_raw = raw.strip()
    if cleaned_raw.startswith("```"):
        lines = cleaned_raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned_raw = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned_raw)
    except json.JSONDecodeError as exc:
        log.error("json_parse_failed_sequence", raw_response=raw[:500], err=str(exc))
        raise exc

    sequence = data.get("sequence", [])

    # ── Safety net: if LLM dropped clips, re-insert them at the correct step ──
    returned_ids = {item["clip_id"] for item in sequence}
    all_ids      = {c["clip_id"] for c in clips}
    missing_ids  = all_ids - returned_ids
    if missing_ids:
        log.warning("llm_sequence_missing_clips", missing=list(missing_ids))
        max_order = max((item.get("order", 0) for item in sequence), default=0)
        for clip in clips:
            if clip["clip_id"] in missing_ids:
                max_order += 1
                sequence.append({
                    "clip_id": clip["clip_id"],
                    "order": max_order,
                    "step": _classify_to_step(clip),
                    "reason": "Re-inserted by fallback (LLM omitted this clip)",
                })

    return sequence


def _classify_to_step(clip: dict[str, Any]) -> int:
    """
    Classify a clip into one of the 7 real-estate steps using keyword matching
    across tags, summary text, AND filename.

    This is the single source of truth for step classification — used by both
    the rule-based fallback sequencer AND as a pre-classification hint injected
    into the LLM sequencing prompt.

    Previously _score_based_sequence only matched exact internal tag strings
    like 'intro_exterior', 'main_living', etc.  Vision LLMs (Gemini/Groq)
    generate natural-language tags ('exterior', 'kitchen', 'bedroom') which
    never matched, causing ALL clips to land in the unclassified bucket (step 8)
    and appear in random score order instead of the 7-step flow.
    """
    tags     = " ".join(t.lower() for t in (clip.get("tags") or []))
    summary  = (clip.get("summary") or "").lower()
    filename = (clip.get("filename") or clip.get("file_path") or "").lower()
    combined = f"{tags} {summary} {filename}"

    # Step 1 — Exterior / Drone
    if any(k in combined for k in [
        "intro_exterior", "exterior", "drone", "aerial", "front", "facade",
        "street", "outside", "driveway", "curb", "street view", "overhead",
    ]):
        return 1

    # Step 2 — Entrance / Foyer
    if any(k in combined for k in [
        "entrance", "entran", "foyer", "hallway", "hall", "door", "lobby",
        "entry", "front door", "porch",
    ]):
        return 2

    # Step 3 — Main Living Area (Living / Kitchen / Dining)
    if any(k in combined for k in [
        "main_living", "living", "kitchen", "dining", "lounge", "family room",
        "cook", "counter", "cabinet", "island", "open plan", "open-plan",
    ]):
        return 3

    # Step 4 — Bedrooms
    if any(k in combined for k in [
        "private_quarters", "bedroom", "bed room", "bed", "master", "guest room",
        "sleeping", "wardrobe", "closet",
    ]):
        return 4

    # Step 5 — Bathrooms
    if any(k in combined for k in [
        "bathroom", "bath", "toilet", "shower", "ensuite", "en-suite",
        "washroom", "vanity",
    ]):
        return 5

    # Step 6 — Outdoor Living
    if any(k in combined for k in [
        "outdoor_living", "pool", "backyard", "back yard", "patio", "deck",
        "garden", "terrace", "alfresco", "bbq", "pergola", "outdoor",
    ]):
        return 6

    # Step 7 — Outro / Closing
    if any(k in combined for k in [
        "outro", "closing", "close", "sunset", "end", "final", "retreat",
    ]):
        return 7

    # Unclassified — sort after all known steps
    return 8


def _score_based_sequence(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Rule-based 7-step real estate sequencer.
    Uses _classify_to_step() for robust keyword-based step assignment
    instead of relying on exact internal tag names.
    """
    clips_by_step: dict[int, list] = {i: [] for i in range(1, 10)}

    for c in clips:
        step = _classify_to_step(c)
        clips_by_step[step].append(c)
        log.debug(
            "rule_based_step_assigned",
            clip_id=c["clip_id"][:8],
            step=step,
            tags=c.get("tags", [])[:4],
            filename=(c.get("filename") or "")[:30],
        )

    final_sequence: list[dict[str, Any]] = []
    order = 1
    for step in range(1, 10):
        # Within each step, sort best-quality clips first
        step_clips = sorted(
            clips_by_step[step],
            key=lambda x: x.get("overall_score") or 0,
            reverse=True,
        )
        for c in step_clips:
            final_sequence.append({
                "clip_id": c["clip_id"],
                "order": order,
                "step": step,
                "reason": f"Step {step} (rule-based). Score: {c.get('overall_score', 0):.1f}",
            })
            order += 1

    return final_sequence
