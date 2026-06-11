"""Check DB state of clips and analysis results."""
import sqlite3
import json

conn = sqlite3.connect('./storage/db/videoedit.db')
cur = conn.cursor()

cur.execute("SELECT id, original_filename, status FROM clips LIMIT 10")
print("Clips:")
for row in cur.fetchall():
    print(f"  {row[0][:8]}... | {row[1][:40]} | status={row[2]}")

cur.execute("SELECT clip_id, tags, summary FROM clip_analyses LIMIT 5")
print("\nAnalysis results:")
for row in cur.fetchall():
    tags = row[1]
    summary = row[2]
    print(f"  clip={row[0][:8]}... | tags={str(tags)[:80]} | summary={str(summary)[:80]}")

conn.close()
