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

    try:
        video = open_video(str(file_path))
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
        return []

    scenes: list[dict[str, Any]] = []
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
