"""
Scene detection using PySceneDetect.
Wraps the library to return a simple list of scene dicts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


def detect_scenes(
    file_path: str | Path,
    threshold: float = 30.0,
    min_scene_len_s: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Run scene detection on a video file.

    Args:
        file_path: Path to video file.
        threshold: ContentDetector threshold (lower = more sensitive).
        min_scene_len_s: Minimum scene length in seconds.

    Returns:
        List of dicts: [{scene_number, start_time, end_time, duration}, ...]
    """
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError:
        log.error("pyscenedetect_not_installed")
        return []

    file_path = Path(file_path)

    # OpenCV struggles massively to decode 4K HEVC on Windows.
    # To fix this, we generate a fast 480p proxy video using ffmpeg and run scene detection on that.
    import tempfile
    import subprocess
    from app.config import get_settings
    settings = get_settings()

    with tempfile.NamedTemporaryFile(suffix=".mp4", dir=settings.temp_dir, delete=False) as tmp:
        proxy_path = Path(tmp.name)

    # Generate 480p proxy (fastest possible settings)
    cmd = [
        settings.ffmpeg_path,
        "-i", str(file_path),
        "-vf", "scale=-2:480",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-an",  # no audio
        "-y",
        str(proxy_path),
    ]
    
    scenes: list[dict[str, Any]] = []
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)

        video = open_video(str(proxy_path))
        scene_manager = SceneManager()
        # AdaptiveDetector is faster than ContentDetector on most clips
        try:
            from scenedetect.detectors import AdaptiveDetector
            scene_manager.add_detector(AdaptiveDetector())
        except ImportError:
            scene_manager.add_detector(ContentDetector(threshold=threshold))
        # Analyse full duration to ensure accurate scene detection on longer clips
        scene_manager.detect_scenes(video, show_progress=False)
        scene_list = scene_manager.get_scene_list()
    except Exception as exc:
        log.warning("scene_detect_failed", path=str(file_path), error=str(exc))
        scene_list = []
    finally:
        try:
            if 'video' in locals():
                try:
                    video.capture.release()
                except Exception:
                    pass
            proxy_path.unlink(missing_ok=True)
        except OSError:
            pass

    for idx, (start, end) in enumerate(scene_list):
        start_s = start.get_seconds()
        end_s = end.get_seconds()
        duration_s = end_s - start_s
        if duration_s < min_scene_len_s:
            continue
        scenes.append(
            {
                "scene_number": idx + 1,
                "start_time": round(start_s, 3),
                "end_time": round(end_s, 3),
                "duration": round(duration_s, 3),
            }
        )

    log.info("scenes_detected", path=str(file_path), count=len(scenes))
    return scenes
