"""
OpenTimelineIO exporter — generates Adobe Premiere-compatible XML and EDL.

Design:
  • Build an OTIO Timeline from our DB entries
  • Export to FCP XML (Premiere-compatible) via otio.adapters.write_to_string
  • Export to EDL via the same adapter system
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


def build_otio_timeline(
    timeline_name: str,
    entries: list[dict[str, Any]],
    clips_meta: dict[str, dict],   # clip_id → {file_path, fps, ...}
    frame_rate: float = 24.0,
) -> Any:
    """
    Build an opentimelineio.schema.Timeline from clip entries.

    entries: [{clip_id, in_point, out_point, order, track}, ...]
    clips_meta: {clip_id: {file_path, fps, width, height, duration}}
    """
    try:
        import opentimelineio as otio
    except ImportError:
        raise RuntimeError(
            "OpenTimelineIO not installed. Run: pip install OpenTimelineIO"
        )

    # Sort entries by order
    sorted_entries = sorted(entries, key=lambda e: e.get("order", 0))

    # Create tracks (group by track number)
    tracks_dict: dict[int, list] = {}
    for entry in sorted_entries:
        track_num = entry.get("track", 0)
        tracks_dict.setdefault(track_num, []).append(entry)

    otio_tracks = []
    for track_num, track_entries in sorted(tracks_dict.items()):
        clips_in_track = []
        for entry in track_entries:
            clip_id = entry["clip_id"]
            meta = clips_meta.get(clip_id, {})
            file_path = meta.get("file_path", "")
            raw_fps = meta.get("fps") or frame_rate
            # Map raw frame rate to standard SMPTE rate to prevent "SMPTE timecode does not support this rate" errors
            standards = [23.976, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0]
            fps = min(standards, key=lambda x: abs(raw_fps - x))

            # Timecode math
            rate = otio.opentime.RationalTime(1, fps)
            start_time = otio.opentime.RationalTime(
                entry["in_point"] * fps, fps
            )
            duration = otio.opentime.RationalTime(
                (entry["out_point"] - entry["in_point"]) * fps, fps
            )
            source_range = otio.opentime.TimeRange(
                start_time=start_time,
                duration=duration,
            )

            # External media reference
            media_ref = otio.schema.ExternalReference(
                target_url=Path(file_path).as_posix() if file_path else "",
                available_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, fps),
                    duration=otio.opentime.RationalTime(
                        (meta.get("duration") or 0) * fps, fps
                    ),
                ),
            )

            clip = otio.schema.Clip(
                name=f"clip_{clip_id[:8]}",
                media_reference=media_ref,
                source_range=source_range,
                metadata={
                    "clip_id": clip_id,
                    "score": entry.get("score"),
                    "reason": entry.get("reason", ""),
                },
            )
            clips_in_track.append(clip)

        track = otio.schema.Track(
            name=f"V{track_num + 1}",
            children=clips_in_track,
            kind=otio.schema.TrackKind.Video,
        )
        otio_tracks.append(track)

    timeline = otio.schema.Timeline(name=timeline_name)
    timeline.tracks.extend(otio_tracks)
    return timeline


def export_fcp_xml(
    otio_timeline: Any,
    output_path: str | Path,
) -> Path:
    """Export OTIO timeline as Final Cut Pro XML (Premiere-compatible)."""
    try:
        import opentimelineio as otio
    except ImportError:
        raise RuntimeError("OpenTimelineIO not installed")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    otio.adapters.write_to_file(otio_timeline, str(output_path), adapter_name="fcp_xml")
    log.info("fcp_xml_exported", path=str(output_path))
    return output_path


def export_otio(
    otio_timeline: Any,
    output_path: str | Path,
) -> Path:
    """Export native OTIO JSON."""
    try:
        import opentimelineio as otio
    except ImportError:
        raise RuntimeError("OpenTimelineIO not installed")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(otio_timeline, str(output_path))
    return output_path


def export_edl(
    otio_timeline: Any,
    output_path: str | Path,
) -> Path:
    """Export CMX 3600 EDL."""
    try:
        import opentimelineio as otio
    except ImportError:
        raise RuntimeError("OpenTimelineIO not installed")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        otio.adapters.write_to_file(otio_timeline, str(output_path), adapter_name="cmx_3600")
    except Exception as exc:
        # EDL has restrictions (single track, SMPTE timecodes) — generate manually if needed
        log.warning("otio_edl_fallback", error=str(exc))
        _write_edl_manual(otio_timeline, output_path)

    return output_path


def _write_edl_manual(otio_timeline: Any, output_path: Path) -> None:
    """
    Fallback EDL writer that generates a valid CMX 3600 EDL manually.
    Supports single video track.
    """
    try:
        import opentimelineio as otio
    except ImportError:
        return

    lines = [f"TITLE: {otio_timeline.name}", "FCM: NON-DROP FRAME", ""]

    event_num = 1
    for track in otio_timeline.tracks:
        if track.kind != otio.schema.TrackKind.Video:
            continue
        timeline_pos = 0.0
        for item in track:
            if not isinstance(item, otio.schema.Clip):
                continue
            sr = item.source_range
            if sr is None:
                continue

            fps = sr.start_time.rate
            src_in = _to_timecode(sr.start_time.value / fps, fps)
            src_out = _to_timecode((sr.start_time.value + sr.duration.value) / fps, fps)
            rec_in = _to_timecode(timeline_pos, fps)
            rec_out = _to_timecode(timeline_pos + sr.duration.value / fps, fps)

            tape_name = f"CLIP{event_num:03d}"
            lines.append(f"{event_num:03d}  {tape_name:<32} V     C        {src_in} {src_out} {rec_in} {rec_out}")
            if item.name:
                lines.append(f"* FROM CLIP NAME: {item.name}")
            lines.append("")

            timeline_pos += sr.duration.value / fps
            event_num += 1

    output_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("edl_manual_written", path=str(output_path), events=event_num - 1)


def _to_timecode(seconds: float, fps: float) -> str:
    """Convert seconds to HH:MM:SS:FF timecode string."""
    fps = fps or 24.0
    total_frames = round(seconds * fps)
    ff = total_frames % int(fps)
    total_seconds = total_frames // int(fps)
    ss = total_seconds % 60
    mm = (total_seconds // 60) % 60
    hh = total_seconds // 3600
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"
