"""
FFmpeg helper utilities — metadata extraction, thumbnails, probing.
All subprocess calls are wrapped so the rest of the app never touches ffmpeg directly.
"""
from __future__ import annotations

import json
import subprocess
import asyncio
import tempfile
from pathlib import Path
from typing import Any

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


# ─── Low-level probe ──────────────────────────────────────────────────────────

def probe(file_path: str | Path) -> dict[str, Any]:
    """Run ffprobe and return the full JSON output."""
    cmd = [
        settings.ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:400]}")
    return json.loads(result.stdout)


async def probe_async(file_path: str | Path) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, probe, file_path)


# ─── Metadata extraction ──────────────────────────────────────────────────────

def extract_metadata(file_path: str | Path) -> dict[str, Any]:
    """
    Return a normalised dict with the most important clip attributes.
    """
    raw = probe(file_path)
    fmt = raw.get("format", {})
    streams = raw.get("streams", [])

    video_stream = next(
        (s for s in streams if s.get("codec_type") == "video"), {}
    )
    audio_stream = next(
        (s for s in streams if s.get("codec_type") == "audio"), {}
    )

    # FPS may be expressed as "60000/1001"
    fps_raw = video_stream.get("r_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    return {
        "duration": float(fmt.get("duration") or video_stream.get("duration") or 0),
        "width": int(video_stream.get("width") or 0) or None,
        "height": int(video_stream.get("height") or 0) or None,
        "fps": round(fps, 3),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name"),
        "bit_rate": int(fmt.get("bit_rate") or 0) or None,
        "nb_frames": int(video_stream.get("nb_frames") or 0) or None,
        "raw_metadata": raw,
    }


async def extract_metadata_async(file_path: str | Path) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, extract_metadata, file_path)


# ─── Thumbnail generation ─────────────────────────────────────────────────────

def generate_thumbnails(
    file_path: str | Path,
    output_dir: str | Path,
    clip_id: str,
    count: int = 5,
    width: int = 320,
    height: int = 180,
) -> list[Path]:
    """
    Extract `count` evenly-spaced thumbnails from the video in a single ffmpeg call.
    Returns list of written thumbnail paths.
    """
    file_path = Path(file_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    meta = extract_metadata(file_path)
    duration = meta.get("duration") or 0.0
    if duration <= 0:
        duration = 1.0
        count = 1

    # Build a select filter that picks exactly `count` frames spread across the video
    # e.g. "select='eq(n\,0)+eq(n\,30)+eq(n\,60)'"
    fps_val  = meta.get("fps") or 25.0
    step = max(1, int(fps_val * duration / count))
    select_expr = "+".join(f"eq(n\\,{i * step})" for i in range(count))

    out_pattern = str(output_dir / f"{clip_id}_thumb_%02d.jpg")
    cmd = [
        settings.ffmpeg_path,
        "-i", str(file_path),
        "-vf", f"select='{select_expr}',scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-vsync", "vfr",
        "-q:v", "5",
        "-y",
        out_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode != 0:
        log.warning("thumbnail_batch_failed", clip_id=clip_id)
        return []

    return sorted(output_dir.glob(f"{clip_id}_thumb_*.jpg"))


async def generate_thumbnails_async(
    file_path: str | Path,
    output_dir: str | Path,
    clip_id: str,
    count: int = 5,
    width: int = 320,
    height: int = 180,
) -> list[Path]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, generate_thumbnails, file_path, output_dir, clip_id, count, width, height
    )


# ─── Frame extraction (for CV analysis) ──────────────────────────────────────

def extract_frames_uniform(
    file_path: str | Path,
    n_frames: int = 30,
    output_dir: str | Path | None = None,
) -> list[Path]:
    """
    Extract n_frames uniformly-spaced frames from the video.
    Uses a temp dir if output_dir is None.
    """
    file_path = Path(file_path)
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(dir=settings.temp_dir))
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    meta = extract_metadata(file_path)
    duration = max(meta.get("duration") or 0.0, 0.01)
    fps_out = n_frames / duration  # virtual fps to get exactly n_frames

    cmd = [
        settings.ffmpeg_path,
        "-i", str(file_path),
        "-vf", f"fps={fps_out:.6f}",
        "-vframes", str(n_frames),
        "-q:v", "3",
        "-y",
        str(output_dir / "frame_%04d.jpg"),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        log.error("frame_extract_failed", stderr=result.stderr[:400])

    return sorted(output_dir.glob("frame_*.jpg"))


# ─── Concatenation helper ─────────────────────────────────────────────────────

def concat_clips(
    clip_paths: list[str | Path],
    output_path: str | Path,
    use_copy: bool = True,
) -> bool:
    """
    Concatenate multiple clips into one using ffmpeg concat demuxer.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", dir=settings.temp_dir, delete=False
    ) as f:
        for cp in clip_paths:
            f.write(f"file '{Path(cp).resolve().as_posix()}'\n")
        list_file = f.name

    codec_args = ["-c", "copy"] if use_copy else ["-c:v", "libx264", "-c:a", "aac"]
    cmd = [
        settings.ffmpeg_path,
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        *codec_args,
        "-y",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=3600)
    Path(list_file).unlink(missing_ok=True)
    if result.returncode != 0:
        log.error("concat_clips_failed", returncode=result.returncode, stderr=result.stderr.decode("utf-8", errors="ignore"))
    return result.returncode == 0


# ─── Trimming helper ──────────────────────────────────────────────────────────

def trim_video(
    input_path: str | Path,
    output_path: str | Path,
    start_s: float,
    end_s: float,
    transcode: bool = True,
) -> bool:
    """
    Trim a video file to [start_s, end_s] segment.

    Seek strategy:
      - transcode=True  : -ss BEFORE -i (fast decoder seek), then re-encode to
                          exact frame boundary. Used for final render output.
      - transcode=False : -ss AFTER -i (slow-but-accurate seek to exact timestamp),
                          then stream-copy. Used for fast auto-trim previews.
                          Accurate because ffmpeg decodes from nearest keyframe.

    If transcode=True, re-encodes to H.264/AAC MP4 at uniform 1280x720@30fps so
    all segments concatenate cleanly with identical codec/timebase.
    """
    input_path  = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    meta      = extract_metadata(input_path)
    has_audio = meta.get("audio_codec") is not None
    duration_s = max(0.0, end_s - start_s)

    if transcode:
        # Fast pre-seek (-ss before -i), then re-encode for frame accuracy
        codec_args = [
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-preset", "superfast",
            "-crf", "23",
            "-r", "30",
            "-ar", "48000",
            "-ac", "2",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30",
            "-movflags", "+faststart",
        ]
        if has_audio:
            cmd = [
                settings.ffmpeg_path,
                "-ss", f"{start_s:.3f}",      # fast seek BEFORE input
                "-i", str(input_path),
                "-t", f"{duration_s:.3f}",
                *codec_args,
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path),
            ]
        else:
            # Silent clip — add null audio so all segments are uniform
            cmd = [
                settings.ffmpeg_path,
                "-ss", f"{start_s:.3f}",
                "-i", str(input_path),
                "-f", "lavfi",
                "-i", "anullsrc=r=48000:cl=stereo",
                "-t", f"{duration_s:.3f}",
                *codec_args,
                "-shortest",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path),
            ]
    else:
        # Accurate seek (-ss AFTER -i) + stream-copy for fast auto-trim previews.
        # FFmpeg decodes from the nearest preceding keyframe then copies from
        # exactly start_s, so the cut is frame-accurate.
        cmd = [
            settings.ffmpeg_path,
            "-i", str(input_path),             # input FIRST
            "-ss", f"{start_s:.3f}",           # accurate seek AFTER input
            "-t", f"{duration_s:.3f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, timeout=600)
    if result.returncode != 0:
        stderr = result.stderr[:600]
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="ignore")
        log.warning("trim_video_failed", start=start_s, end=end_s, stderr=stderr)
    return result.returncode == 0
