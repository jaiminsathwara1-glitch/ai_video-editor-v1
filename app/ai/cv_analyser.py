"""
Computer Vision analysis — pure OpenCV, no LLM calls.

Detects poor-quality video segments across 6 dimensions:

  1. Blur       — Laplacian variance + Tenengrad gradient energy (per-frame)
  2. Shake      — Phase-correlation camera jitter / translational acceleration
  3. Noise      — Local-variance noise estimator (Immerkær method)  [informational]
  4. Artifacts  — DCT blockiness detector (compression / encoding)  [informational]
  5. Exposure   — Per-frame luminance histogram (over/under)        [informational]
  6. Frozen     — Frame-difference frozen/static detector           [informational]

Only Blur and Shake are primary quality gates for `usable_ranges`.  The other
dimensions contribute to the overall_score but do NOT gate out segments — this
ensures only genuinely blurry or shaky footage is cut, and the maximum amount
of usable video is preserved for the timeline.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import structlog

from app.services.ffmpeg_utils import extract_frames_uniform

log = structlog.get_logger(__name__)

# ── Analysis resolution ───────────────────────────────────────────────────────
N_ANALYSIS_FRAMES  = 120     # doubled sample count — halves blind-spot between samples
FLOW_WIDTH         = 480     # downscale width for phase-correlation
SMOOTH_WINDOW      = 15      # wide window — requires ~15 consecutive stable frames
USABLE_MIN_SECS    = 2.0     # drop segments shorter than 2 s — kills micro-segments

# ── Per-dimension pass/fail thresholds ───────────────────────────────────────
# Blur: frames below BLUR_RELATIVE_FLOOR × clip-best are blurry.
# 0.18 — stricter than 0.08; cuts all frames that are noticeably soft.
BLUR_LAP_WEIGHT     = 0.6
BLUR_TEN_WEIGHT     = 0.4
BLUR_RELATIVE_FLOOR = 0.18   # 18% of clip-best — strict but not over-aggressive

# Shake: max translational acceleration (pixels/frame² at FLOW_WIDTH).
# 1.5 — tighter; any noticeable camera jerk is cut.
SHAKE_JITTER_MAX   = 1.5

# Noise / Blockiness / Exposure / Frozen — INFORMATIONAL ONLY.
# These do NOT gate usable_ranges; they only feed overall_score.
NOISE_SIGMA_MAX    = 35.0
BLOCK_SCORE_MAX    = 12.0
EXPOSE_LOW         = 15
EXPOSE_HIGH        = 245
FROZEN_DIFF_MIN    = 0.3

# Clip-level flag thresholds
CLIP_BAD_FRACTION  = 0.60


# ─── Public entry point ───────────────────────────────────────────────────────

def analyse_clip_cv(file_path: str | Path, clip_id: str) -> dict[str, Any]:
    """
    Run full multi-dimension quality analysis on a video file.
    Returns a dict compatible with ClipAnalysis fields.
    """
    file_path = Path(file_path)
    log.info("cv_analysis_start", clip_id=clip_id, n_frames=N_ANALYSIS_FRAMES)

    gray_frames, color_frames = _extract_frames(file_path, clip_id)
    if not gray_frames:
        log.warning("no_frames_extracted", clip_id=clip_id)
        return _empty_result()

    n = len(gray_frames)

    # ── Per-frame scores for each quality dimension ───────────────────────────
    pf_blur    = _per_frame_blur(gray_frames)
    pf_jitter  = _per_frame_jitter(gray_frames)
    pf_noise   = _per_frame_noise(gray_frames)
    pf_block   = _per_frame_blockiness(gray_frames)
    pf_lum     = _per_frame_luminance(gray_frames)
    pf_diff    = _per_frame_frame_diff(gray_frames)

    # ── Per-frame pass/fail flags ─────────────────────────────────────────────
    blur_arr   = np.array(pf_blur,   dtype=np.float64)
    # pf_jitter now returns exactly n values (edge-replicated, not zero-padded)
    jitter_arr = np.array(pf_jitter, dtype=np.float64)
    noise_arr  = np.array(pf_noise,  dtype=np.float64)
    block_arr  = np.array(pf_block,  dtype=np.float64)
    lum_arr    = np.array(pf_lum,    dtype=np.float64)
    diff_arr   = _align(pf_diff, n)

    max_blur   = blur_arr.max() if blur_arr.size > 0 else 1.0
    max_blur   = max_blur if max_blur > 1e-9 else 1.0

    flag_blur   = (blur_arr / max_blur) >= BLUR_RELATIVE_FLOOR
    flag_shake  = jitter_arr <= SHAKE_JITTER_MAX
    flag_noise  = noise_arr  <= NOISE_SIGMA_MAX
    flag_block  = block_arr  <= BLOCK_SCORE_MAX
    flag_expose = (lum_arr   >= EXPOSE_LOW) & (lum_arr <= EXPOSE_HIGH)
    flag_frozen = diff_arr   >= FROZEN_DIFF_MIN

    # ── Clip-level aggregate scores (0-10) ────────────────────────────────────
    h, w = gray_frames[0].shape[:2]
    pixel_ratio  = (w * h) / (1920 * 1080)
    scale_factor = max(15.0, 60.0 * math.sqrt(pixel_ratio))
    clip_blur_raw = float(np.percentile(blur_arr, 20)) if blur_arr.size else 0.0
    blur_norm  = float(np.clip(clip_blur_raw / scale_factor, 0.0, 10.0))

    clip_jitter = float(np.percentile(jitter_arr, 80)) if jitter_arr.size else 0.0
    shake_norm  = float(np.clip(10.0 - (clip_jitter / SHAKE_JITTER_MAX) * 10.0, 0.0, 10.0))

    noise_mean  = float(np.mean(noise_arr)) if noise_arr.size else 0.0
    noise_norm  = float(np.clip(10.0 - (noise_mean / NOISE_SIGMA_MAX) * 10.0, 0.0, 10.0))

    block_mean  = float(np.mean(block_arr)) if block_arr.size else 0.0
    block_norm  = float(np.clip(10.0 - (block_mean / BLOCK_SCORE_MAX) * 10.0, 0.0, 10.0))

    mean_lum    = float(np.mean(lum_arr)) if lum_arr.size else 128.0
    expose_norm = float(10.0 * math.exp(-((mean_lum - 128) ** 2) / (2 * 70 ** 2)))

    motion_raw  = float(np.mean(diff_arr)) if diff_arr.size else 0.0
    motion_norm = float(np.clip(motion_raw / 5.0, 0.0, 10.0))

    # Weighted overall quality (all six dimensions)
    overall = round(
        blur_norm   * 0.30
        + shake_norm  * 0.25
        + noise_norm  * 0.15
        + block_norm  * 0.10
        + expose_norm * 0.15
        + motion_norm * 0.05,
        2,
    )

    # ── Clip-level issue flags ────────────────────────────────────────────────
    is_blurry      = float((~flag_blur).sum())   / n > CLIP_BAD_FRACTION
    is_shaky       = float((~flag_shake).sum())  / n > CLIP_BAD_FRACTION
    is_overexposed = float((lum_arr > EXPOSE_HIGH).sum()) / n > CLIP_BAD_FRACTION
    is_underexposed= float((lum_arr < EXPOSE_LOW ).sum()) / n > CLIP_BAD_FRACTION

    # ── Perceptual hash (middle frame) ────────────────────────────────────────
    p_hash = _perceptual_hash(gray_frames[n // 2])

    # ── Usable ranges — the good segments to keep ─────────────────────────────
    try:
        duration = _get_duration(file_path)
        usable_ranges = _detect_usable_ranges(
            flag_blur, flag_shake, flag_noise,
            flag_block, flag_expose, flag_frozen,
            duration, n,
        )
    except Exception as exc:
        log.warning("usable_range_error", clip_id=clip_id, err=str(exc))
        usable_ranges = []

    log.info(
        "cv_analysis_done",
        clip_id=clip_id,
        overall=overall,
        blur=round(blur_norm, 2),
        shake=round(shake_norm, 2),
        noise=round(noise_norm, 2),
        blocks=round(block_norm, 2),
        expose=round(expose_norm, 2),
        usable_segments=len(usable_ranges),
    )

    return {
        "blur_score":       round(blur_norm, 2),
        "shake_score":      round(shake_norm, 2),
        "exposure_score":   round(expose_norm, 2),
        "overall_score":    overall,
        "is_blurry":        is_blurry,
        "is_shaky":         is_shaky,
        "is_overexposed":   is_overexposed,
        "is_underexposed":  is_underexposed,
        "perceptual_hash":  p_hash,
        "usable_ranges":    usable_ranges,
        "motion_score":     round(motion_norm, 2),
    }


# ─── Frame extraction ─────────────────────────────────────────────────────────

def _extract_frames(
    file_path: Path, clip_id: str
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """
    Extract N_ANALYSIS_FRAMES uniformly-spaced frames.
    Returns (gray_frames, color_frames). Falls back to ffmpeg on failure.
    """
    cap    = cv2.VideoCapture(str(file_path))
    opened = cap.isOpened()
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if opened else 0

    gray_frames:  list[np.ndarray] = []
    color_frames: list[np.ndarray] = []

    if opened and total > 2:
        indices = np.linspace(0, total - 2, N_ANALYSIS_FRAMES, dtype=int)
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            color_frames.append(frame)
            gray_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    cap.release()

    # Fallback: disk-based extraction via ffmpeg
    if not gray_frames:
        log.info("cv_ffmpeg_fallback", clip_id=clip_id)
        disk_frames = extract_frames_uniform(file_path, n_frames=N_ANALYSIS_FRAMES)
        for f in disk_frames:
            img = cv2.imread(str(f))
            if img is not None:
                color_frames.append(img)
                gray_frames.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        if disk_frames:
            try:
                disk_frames[0].parent.rmdir()
            except OSError:
                pass

    return gray_frames, color_frames


# ─── 1. Blur (Laplacian + Tenengrad) ─────────────────────────────────────────

def _per_frame_blur(gray_frames: list[np.ndarray]) -> list[float]:
    """Combined blur measure per frame. Higher = sharper."""
    if not gray_frames:
        return []
    lap = np.array([cv2.Laplacian(f, cv2.CV_64F).var() for f in gray_frames])
    gx  = [cv2.Sobel(f, cv2.CV_64F, 1, 0, ksize=3) for f in gray_frames]
    gy  = [cv2.Sobel(f, cv2.CV_64F, 0, 1, ksize=3) for f in gray_frames]
    ten = np.array([float(np.mean(gx[i]**2 + gy[i]**2)) for i in range(len(gray_frames))])

    def _norm01(arr: np.ndarray) -> np.ndarray:
        lo, hi = arr.min(), arr.max()
        return np.ones_like(arr) if (hi - lo) < 1e-9 else (arr - lo) / (hi - lo)

    combined = _norm01(lap) * BLUR_LAP_WEIGHT + _norm01(ten) * BLUR_TEN_WEIGHT
    # Re-scale to keep cross-clip comparability (preserves raw magnitude)
    lap_mean = float(lap.mean()) if lap.size > 0 else 1.0
    return (combined * lap_mean).tolist()


# ─── 2. Shake (phase-correlation jitter) ─────────────────────────────────────

def _downscale(f: np.ndarray) -> np.ndarray:
    h, w = f.shape[:2]
    if w <= FLOW_WIDTH:
        return f
    s = FLOW_WIDTH / w
    return cv2.resize(f, (FLOW_WIDTH, int(h * s)), interpolation=cv2.INTER_AREA)


def _phase_corr(prev: np.ndarray, curr: np.ndarray) -> tuple[float, float]:
    """Sub-pixel global translation via DFT phase correlation."""
    h, w   = prev.shape[:2]
    win    = cv2.createHanningWindow((w, h), cv2.CV_64F)
    (dx, dy), _ = cv2.phaseCorrelate(
        prev.astype(np.float64) * win,
        curr.astype(np.float64) * win,
    )
    return float(dx), float(dy)


def _per_frame_jitter(gray_frames: list[np.ndarray]) -> list[float]:
    """
    Per-frame translational jitter = acceleration of camera trajectory.
    Returns exactly len(gray_frames) values.

    IMPORTANT: edge frames use the nearest computed jitter (edge-replication),
    NOT zero-padding. Zero-padding caused the first and last frames to always
    be marked as 'stable' (jitter=0 <= threshold), letting shaky starts/ends
    slip into usable ranges.
    """
    n = len(gray_frames)
    if n < 3:
        # Can't compute acceleration with fewer than 3 frames.
        # Mark all as shaky (high jitter) so they don't contaminate usable ranges.
        return [SHAKE_JITTER_MAX * 2.0] * n

    small = [_downscale(f) for f in gray_frames]
    # velocities[i] = displacement between frame i and frame i+1
    vels: list[tuple[float, float]] = [
        _phase_corr(small[i], small[i + 1]) for i in range(n - 1)
    ]
    # accelerations[i] = |velocity[i+1] - velocity[i]| (length = n-2)
    accs = [
        math.sqrt((vels[i+1][0] - vels[i][0])**2 + (vels[i+1][1] - vels[i][1])**2)
        for i in range(len(vels) - 1)
    ]
    # Pad to n values using edge-replication (NOT zeros):
    #   frame 0    -> accs[0]     (same as second frame)
    #   frame n-1  -> accs[-1]    (same as second-to-last frame)
    return [accs[0]] + accs + [accs[-1]]  # length = (n-2) + 2 = n


# ─── 3. Noise (Immerkær estimator) ───────────────────────────────────────────

def _noise_sigma(gray: np.ndarray) -> float:
    """
    Estimate image noise using the Immerkær (1996) method.
    Returns sigma in grayscale units (0-255). Higher = noisier.
    Robust to scene content — only responds to high-frequency spatial noise.
    """
    h, w = gray.shape[:2]
    if h < 3 or w < 3:
        return 0.0
    # 3×3 Laplacian kernel (detects noise without edges)
    kernel = np.array(
        [[ 1, -2,  1],
         [-2,  4, -2],
         [ 1, -2,  1]], dtype=np.float64
    )
    filtered = cv2.filter2D(gray.astype(np.float64), -1, kernel)
    sigma = math.sqrt(math.pi / 2.0) * float(np.mean(np.abs(filtered))) / 6.0
    return sigma


def _per_frame_noise(gray_frames: list[np.ndarray]) -> list[float]:
    return [_noise_sigma(f) for f in gray_frames]


# ─── 4. Compression Artifacts (DCT blockiness) ───────────────────────────────

def _blockiness_score(gray: np.ndarray, block: int = 8) -> float:
    """
    Measure DCT blockiness — the average absolute difference at 8×8 block
    boundaries (horizontal + vertical). Higher = more compression artifacts.
    Detects JPEG / H.264 mosquito noise and macro-blocking.
    """
    h, w = gray.shape[:2]
    f    = gray.astype(np.float64)

    # Vertical block boundaries: pixel difference across column borders
    cols = list(range(block - 1, w - 1, block))
    v_scores: list[float] = []
    for c in cols:
        diff = np.abs(f[:, c] - f[:, c + 1])
        v_scores.append(float(diff.mean()))

    # Horizontal block boundaries: pixel difference across row borders
    rows = list(range(block - 1, h - 1, block))
    h_scores: list[float] = []
    for r in rows:
        diff = np.abs(f[r, :] - f[r + 1, :])
        h_scores.append(float(diff.mean()))

    if not v_scores and not h_scores:
        return 0.0

    return float(np.mean(v_scores + h_scores))


def _per_frame_blockiness(gray_frames: list[np.ndarray]) -> list[float]:
    return [_blockiness_score(f) for f in gray_frames]


# ─── 5. Exposure (per-frame luminance) ───────────────────────────────────────

def _per_frame_luminance(gray_frames: list[np.ndarray]) -> list[float]:
    """Mean grayscale luminance per frame (0-255)."""
    return [float(np.mean(f)) for f in gray_frames]


# ─── 6. Frozen / static frame detector ───────────────────────────────────────

def _per_frame_frame_diff(gray_frames: list[np.ndarray]) -> list[float]:
    """
    Mean absolute pixel difference between consecutive frames.
    Returns n-1 values. Very low values indicate frozen / duplicate frames.
    """
    if len(gray_frames) < 2:
        return [0.0] * max(0, len(gray_frames))
    diffs = [
        float(np.mean(np.abs(
            gray_frames[i].astype(np.int16) - gray_frames[i - 1].astype(np.int16)
        )))
        for i in range(1, len(gray_frames))
    ]
    return [diffs[0]] + diffs   # pad head so length = n


# ─── Utility: align a list to length n ───────────────────────────────────────

def _align(values: list[float], n: int) -> np.ndarray:
    """Pad or truncate a list to exactly n elements, then return as ndarray."""
    arr = np.zeros(n, dtype=np.float64)
    src = values[:n]
    arr[: len(src)] = src
    return arr


# ─── Usable range detection ───────────────────────────────────────────────────

def _detect_usable_ranges(
    flag_blur:   np.ndarray,
    flag_shake:  np.ndarray,
    flag_noise:  np.ndarray,
    flag_block:  np.ndarray,
    flag_expose: np.ndarray,
    flag_frozen: np.ndarray,
    duration:    float,
    n:           int,
) -> list[dict]:
    """
    Combine per-frame quality flags → usable time segments.

    PRIMARY gates  (must pass): blur AND shake.
    SECONDARY flags (informational): noise, blockiness, exposure, frozen.
      — Secondary flags are NOT used as hard gates.  They only inform the
        overall_score.  This ensures only genuinely blurry or shaky footage
        is removed; the rest of the clip is kept intact.

    A median-vote smoothing window eliminates single-frame blips.
    Returns [{start: float, end: float}, ...] in seconds.
    """
    if duration <= 0 or n == 0:
        return []

    frame_dt = duration / n

    # ── PRIMARY quality gate: blur AND shake only ─────────────────────────────
    # A frame is usable if it is not blurry AND not shaky.
    usable = (flag_blur & flag_shake).astype(np.int8)

    # Median smoothing — small window so we don't over-merge bad regions
    w   = (SMOOTH_WINDOW | 1)   # ensure odd
    pad = w // 2
    padded   = np.pad(usable, pad, mode="edge")
    smoothed = np.array(
        [np.median(padded[i : i + w]) for i in range(n)], dtype=np.float64
    )
    usable_smooth = smoothed >= 0.5

    # ── If no frames pass the quality gate, this clip has no usable portion ────
    # Return [] — the timeline builder will skip this clip entirely.
    # We intentionally do NOT fall back to 'keep the whole clip' because that
    # would undo all the blur/shake filtering work.
    good_fraction = float(usable_smooth.sum()) / n
    if good_fraction < 0.01:
        log.info(
            "usable_range_none",
            msg="clip has no frames passing blur+shake gates — excluded from timeline",
            good_fraction=round(good_fraction, 4),
        )
        return []

    # ── Build contiguous ranges from usable frame mask ────────────────────────
    ranges: list[dict] = []
    in_range  = False
    start_idx = 0

    for i, good in enumerate(usable_smooth):
        if good and not in_range:
            start_idx = i
            in_range  = True
        elif not good and in_range:
            start_t = round(start_idx * frame_dt, 3)
            end_t   = round(i * frame_dt, 3)
            if end_t - start_t >= USABLE_MIN_SECS:
                ranges.append({"start": start_t, "end": end_t})
            in_range = False

    if in_range:
        start_t = round(start_idx * frame_dt, 3)
        end_t   = round(duration, 3)
        if end_t - start_t >= USABLE_MIN_SECS:
            ranges.append({"start": start_t, "end": end_t})

    # NOTE: Gap merging intentionally removed.
    # Merging gaps between segments was importing shaky middle sections
    # into the output. Each stable segment must stand on its own.
    return ranges


# ─── Exposure (clip-level) ────────────────────────────────────────────────────

def _exposure_score(gray_frames: list[np.ndarray]) -> tuple[float, bool, bool]:
    """Clip-level exposure summary (kept for backwards compatibility)."""
    means    = [float(np.mean(f)) for f in gray_frames]
    mean_lum = float(np.mean(means))
    is_over  = mean_lum > EXPOSE_HIGH
    is_under = mean_lum < EXPOSE_LOW
    score    = 10.0 * math.exp(-((mean_lum - 128) ** 2) / (2 * 70 ** 2))
    return round(float(score), 2), is_over, is_under


# ─── Duration helper ──────────────────────────────────────────────────────────

def _get_duration(file_path: Path) -> float:
    from app.services.ffmpeg_utils import extract_metadata
    meta = extract_metadata(file_path)
    return float(meta.get("duration") or 0.0)


# ─── Perceptual hash ──────────────────────────────────────────────────────────

def _perceptual_hash(gray_frame: np.ndarray, hash_size: int = 16) -> str:
    """dHash — gradient-based perceptual fingerprint for duplicate detection."""
    resized = cv2.resize(gray_frame, (hash_size + 1, hash_size))
    diff    = resized[:, 1:] > resized[:, :-1]
    val     = 0
    for bit in diff.flatten():
        val = (val << 1) | int(bit)
    return format(val, "064x")


# ─── Empty result ─────────────────────────────────────────────────────────────

def _empty_result() -> dict[str, Any]:
    return {
        "blur_score":      None,
        "shake_score":     None,
        "exposure_score":  None,
        "overall_score":   None,
        "is_blurry":       False,
        "is_shaky":        False,
        "is_overexposed":  False,
        "is_underexposed": False,
        "perceptual_hash": None,
        "usable_ranges":   [],
        "motion_score":    None,
    }


# ─── Duplicate detection (public API) ────────────────────────────────────────

def hamming_distance(hash1: str, hash2: str) -> int:
    """Count differing bits between two hex hashes."""
    try:
        return bin(int(hash1, 16) ^ int(hash2, 16)).count("1")
    except (ValueError, TypeError):
        return 999


def find_duplicates(
    hashes: dict[str, str],
    threshold: int = 8,
) -> list[tuple[str, str]]:
    """
    Given {clip_id: phash_hex}, return pairs of likely-duplicate clip IDs.
    threshold: max Hamming distance to consider duplicate (default 8 / 256 bits).
    """
    ids   = list(hashes.keys())
    pairs: list[tuple[str, str]] = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if hamming_distance(hashes[ids[i]], hashes[ids[j]]) <= threshold:
                pairs.append((ids[i], ids[j]))
    return pairs
