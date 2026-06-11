import sqlite3
conn = sqlite3.connect('./storage/db/videoedit.db')
c = conn.cursor()
c.execute("DELETE FROM clips WHERE mime_type = 'application/zip' AND status = 'uploading'")
conn.commit()
print("Deleted stuck placeholder")
