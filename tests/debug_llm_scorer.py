"""
Debug script: runs tag_and_summarise() exactly as the Celery worker does.
Prints the full error traceback so we can see WHY it falls back to rules.

Run: .\venv\Scripts\python tests\debug_llm_scorer.py
"""
import sys
import traceback
from pathlib import Path

# Add project root so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3

# ── Load a real clip from the DB ──────────────────────────────────────────────
conn = sqlite3.connect("./storage/db/videoedit.db")
cur = conn.cursor()
cur.execute(
    "SELECT id, project_id, duration, width, height, fps, audio_codec, original_filename "
    "FROM clips WHERE status='analysed' LIMIT 1"
)
row = cur.fetchone()
conn.close()

if not row:
    print("[DEBUG] No analysed clip found in DB")
    sys.exit(1)

clip_id, project_id, duration, width, height, fps, audio_codec, original_filename = row
print(f"[DEBUG] Using clip: {clip_id}")
print(f"[DEBUG]   project_id      : {project_id}")
print(f"[DEBUG]   original_filename: {original_filename}")

# ── Check thumbnails ──────────────────────────────────────────────────────────
from app.config import get_settings
settings = get_settings()

thumb_dir = Path(settings.thumbnail_dir) / project_id
print(f"\n[DEBUG] thumbnail_dir setting : {settings.thumbnail_dir}")
print(f"[DEBUG] Full thumb_dir path   : {thumb_dir}")
print(f"[DEBUG] thumb_dir exists?     : {thumb_dir.exists()}")

if thumb_dir.exists():
    all_files = list(thumb_dir.glob(f"{clip_id}_thumb_*.jpg"))
    print(f"[DEBUG] Thumbnails found for this clip: {len(all_files)}")
    for f in all_files:
        print(f"  {f}")
else:
    print("[DEBUG] Thumbnail directory does NOT exist!")
    print("        Available dirs:", [str(d) for d in Path(settings.thumbnail_dir).iterdir()] if Path(settings.thumbnail_dir).exists() else "parent dir missing")

# ── Now call the actual LLM scorer ────────────────────────────────────────────
from app.ai.llm_scorer import _llm_tag_and_summarise, _rule_based_tags

tag_meta = {
    "clip_id": clip_id,
    "project_id": project_id,
    "duration": duration,
    "width": width,
    "height": height,
    "fps": fps,
    "audio_codec": audio_codec,
    "filename": original_filename,
    "blur_score": 7.0,
    "shake_score": 6.5,
    "exposure_score": 7.0,
    "motion_score": 3.0,
    "overall_score": 7.0,
    "usable_ranges": [{"start": 0.0, "end": float(duration or 10)}],
    "scene_count": 2,
    "transcript": "",
}

print("\n[DEBUG] Calling _llm_tag_and_summarise(analysis_mode='groq_vision') ...")
print("-" * 60)

try:
    result = _llm_tag_and_summarise(tag_meta, analysis_mode="groq_vision")
    print("\n[DEBUG] SUCCESS!")
    print(f"  tags   : {result['tags']}")
    print(f"  summary: {result['summary']}")
except Exception as exc:
    print(f"\n[DEBUG] EXCEPTION: {type(exc).__name__}: {exc}")
    print("\n[DEBUG] Full traceback:")
    traceback.print_exc()
    print("\n[DEBUG] Rule-based fallback result:")
    rb = _rule_based_tags(tag_meta)
    print(f"  tags   : {rb['tags']}")
    print(f"  summary: {rb['summary']}")
