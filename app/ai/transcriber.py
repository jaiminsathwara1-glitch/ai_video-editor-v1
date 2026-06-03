"""
Whisper transcription helper.

Note: Whisper runs locally — no video/frames are sent to any external service.
Only the extracted audio is processed.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

_whisper_model = None


def _get_model():
    """Lazy-load Whisper model (cached at module level)."""
    global _whisper_model
    if _whisper_model is None:
        import whisper  # type: ignore
        log.info("loading_whisper_model", model=settings.whisper_model)
        _whisper_model = whisper.load_model(settings.whisper_model)
    return _whisper_model


def transcribe_clip(file_path: str | Path) -> dict[str, Any]:
    """
    Extract audio from video and run Whisper transcription.

    Returns:
        {text: str, segments: [{start, end, text}, ...], language: str}
    """
    file_path = Path(file_path)

    # Extract audio to temp WAV file
    with tempfile.NamedTemporaryFile(
        suffix=".wav", dir=settings.temp_dir, delete=False
    ) as tmp:
        audio_path = Path(tmp.name)

    try:
        _extract_audio(file_path, audio_path)
        model = _get_model()
        result = model.transcribe(str(audio_path), word_timestamps=False)
    except Exception as exc:
        log.warning("transcription_failed", file=str(file_path), error=str(exc))
        return {"text": "", "segments": [], "language": ""}
    finally:
        audio_path.unlink(missing_ok=True)

    segments = [
        {
            "start": round(s["start"], 3),
            "end": round(s["end"], 3),
            "text": s["text"].strip(),
        }
        for s in result.get("segments", [])
    ]

    return {
        "text": result.get("text", "").strip(),
        "segments": segments,
        "language": result.get("language", ""),
    }


def _extract_audio(video_path: Path, audio_path: Path) -> None:
    cmd = [
        settings.ffmpeg_path,
        "-i", str(video_path),
        "-ac", "1",          # mono
        "-ar", "16000",      # 16 kHz (Whisper default)
        "-vn",               # no video
        "-y",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr[:200]}")
