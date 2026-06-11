"""Read last 100 lines of server.log safely."""
from pathlib import Path

log_path = Path("./server.log")
if log_path.exists():
    try:
        # Try reading with utf-16 since it has been failing on utf-8
        content = log_path.read_text(encoding="utf-16")
    except Exception:
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print("Failed to read log file:", e)
            content = ""
    
    lines = content.splitlines()
    print(f"--- Server Log (Last 60 lines, total {len(lines)} lines) ---")
    for line in lines[-60:]:
        print(line)
else:
    print("server.log does not exist")
