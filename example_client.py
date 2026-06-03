#!/usr/bin/env python
"""
Example client script demonstrating the full workflow:
  1. Create a project
  2. Upload a clip (simple upload)
  3. Start analysis
  4. Poll until analysis complete
  5. Generate timeline
  6. Export to XML + EDL
  7. Download the XML

Usage:
  python example_client.py path/to/your/clip.mp4
"""
from __future__ import annotations

import sys
import time
import requests

BASE_URL = "http://localhost:8000/api/v1"


def main(video_path: str) -> None:
    print("=== AI Video Rough-Cut Platform — Example Client ===\n")

    # ── 1. Create project ─────────────────────────────────────────────────────
    print("[1] Creating project...")
    r = requests.post(f"{BASE_URL}/projects/", json={"name": "My Test Project"})
    r.raise_for_status()
    project = r.json()
    project_id = project["id"]
    print(f"    Project ID: {project_id}")

    # ── 2. Upload clip ────────────────────────────────────────────────────────
    print(f"\n[2] Uploading clip: {video_path}")
    with open(video_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/clips/upload/simple",
            params={"project_id": project_id},
            files={"file": (video_path.split("/")[-1], f, "video/mp4")},
        )
    r.raise_for_status()
    clip = r.json()
    clip_id = clip["id"]
    print(f"    Clip ID: {clip_id}  Duration: {clip.get('duration', '?')}s")

    # ── 3. Start analysis ─────────────────────────────────────────────────────
    print("\n[3] Starting analysis...")
    r = requests.post(f"{BASE_URL}/analysis/clip/{clip_id}/start")
    r.raise_for_status()
    task_id = r.json()["task_id"]
    print(f"    Task ID: {task_id}")

    # ── 4. Poll status ────────────────────────────────────────────────────────
    print("\n[4] Waiting for analysis...")
    for attempt in range(60):
        time.sleep(5)
        r = requests.get(f"{BASE_URL}/analysis/task/{task_id}/status")
        status = r.json()["status"]
        progress = r.json().get("progress") or {}
        print(f"    [{attempt * 5}s] Status: {status}  {progress}")
        if status in ("SUCCESS", "FAILURE"):
            break

    # ── 5. Print scores ───────────────────────────────────────────────────────
    print("\n[5] Clip analysis results:")
    r = requests.get(f"{BASE_URL}/analysis/project/{project_id}/scores")
    for clip_score in r.json():
        print(f"    Clip {clip_score['clip_id'][:8]}...")
        print(f"      Score:   {clip_score['score']}")
        print(f"      Tags:    {clip_score['tags']}")
        print(f"      Summary: {clip_score['summary']}")

    # ── 6. Generate timeline ──────────────────────────────────────────────────
    print("\n[6] Generating rough-cut timeline...")
    r = requests.post(
        f"{BASE_URL}/timelines/generate",
        json={"project_id": project_id, "name": "My Rough Cut", "min_score": 3.0},
    )
    r.raise_for_status()
    timeline = r.json()
    timeline_id = timeline["id"]
    print(f"    Timeline ID:       {timeline_id}")
    print(f"    Total duration:    {timeline['total_duration']}s")
    print(f"    Clips used:        {timeline['clip_count']}")

    # ── 7. Export XML + EDL ───────────────────────────────────────────────────
    print("\n[7] Exporting XML + EDL...")
    r = requests.post(f"{BASE_URL}/timelines/{timeline_id}/export/all")
    r.raise_for_status()
    export_task_id = r.json()["task_id"]

    for attempt in range(20):
        time.sleep(3)
        r = requests.get(f"{BASE_URL}/analysis/task/{export_task_id}/status")
        status = r.json()["status"]
        print(f"    [{attempt * 3}s] Export status: {status}")
        if status in ("SUCCESS", "FAILURE"):
            break

    # ── 8. Download XML ───────────────────────────────────────────────────────
    print("\n[8] Downloading XML...")
    r = requests.get(f"{BASE_URL}/timelines/{timeline_id}/download/xml")
    if r.status_code == 200:
        out_file = f"timeline_{timeline_id[:8]}.xml"
        with open(out_file, "wb") as f:
            f.write(r.content)
        print(f"    [OK] Saved to: {out_file}")
    else:
        print(f"    [WARNING] Download failed: {r.status_code} — {r.text[:200]}")

    print("\n=== Done! ===")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python example_client.py path/to/clip.mp4")
        sys.exit(1)
    main(sys.argv[1])
