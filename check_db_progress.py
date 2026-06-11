import sqlite3
conn = sqlite3.connect('./storage/db/videoedit.db')
c = conn.cursor()
c.execute("SELECT original_filename FROM clips WHERE mime_type = 'application/zip' ORDER BY created_at DESC LIMIT 1")
print(c.fetchone()[0])
