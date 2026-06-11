"""
Debug run analysis for the latest project.
This runs it synchronously so we can see the exact traceback in the console.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.workers.analysis_tasks import analyse_project
import sqlite3

conn = sqlite3.connect("./storage/db/videoedit.db")
cur = conn.cursor()
cur.execute("SELECT id, name FROM projects ORDER BY created_at DESC LIMIT 1")
row = cur.fetchone()
conn.close()

if not row:
    print("[ERROR] No projects found in DB")
    sys.exit(1)

project_id, name = row
print(f"[INFO] Latest project: {name} (id: {project_id})")

# Run it synchronously!
print(f"[INFO] Triggering analysis task synchronously for project: {project_id}...")
try:
    # Run the worker function directly without Celery's apply_async
    res = analyse_project(project_id, analysis_mode="groq_vision")
    print("[SUCCESS] Dispatched task IDs:", res)
except Exception as e:
    import traceback
    traceback.print_exc()
