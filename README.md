# AI Video Rough-Cut Platform

Production-ready Python backend for AI-assisted video editing.  
**Upload 80–300 raw 4K60 clips → analyse with CV + Whisper → AI-generated rough-cut → export to Adobe Premiere XML.**

---

## Architecture Overview

```
┌─────────────┐   HTTP    ┌──────────────────────────────────────────┐
│  Client /   │ ────────▶ │  FastAPI  (async, uvicorn)               │
│  Premiere   │           │  /api/v1/{projects,clips,analysis,       │
└─────────────┘           │            timelines}                    │
                          └────────────────┬─────────────────────────┘
                                           │ Celery tasks
                          ┌────────────────▼─────────────────────────┐
                          │  Redis (broker + result backend)          │
                          └────────────────┬─────────────────────────┘
                                           │
                    ┌──────────────────────▼──────────────────────────┐
                    │  Celery Workers                                  │
                    │  ├── analysis_tasks  (blur/shake/CV/Whisper/LLM)│
                    │  └── export_tasks    (OTIO → XML / EDL)         │
                    └────────────────────────────────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────────┐
                          │  SQLite + aiosqlite (→ Postgres ready)    │
                          └──────────────────────────────────────────┘
```

### Directory Structure

```
ai-video_editing/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings (pydantic-settings)
│   ├── database.py          # Async SQLAlchemy engine + get_db
│   ├── logging_config.py    # structlog setup
│   ├── models/
│   │   ├── project.py       # Project ORM
│   │   ├── clip.py          # Clip + ClipChunk ORM
│   │   ├── analysis.py      # ClipAnalysis ORM
│   │   └── timeline.py      # Timeline ORM
│   ├── schemas/
│   │   ├── project.py       # Pydantic schemas
│   │   ├── clip.py
│   │   ├── analysis.py
│   │   └── timeline.py
│   ├── routes/
│   │   ├── projects.py      # CRUD endpoints
│   │   ├── clips.py         # Upload endpoints (chunked + simple)
│   │   ├── analysis.py      # Trigger / poll / scores
│   │   └── timelines.py     # Generate / export / download
│   ├── services/
│   │   ├── ffmpeg_utils.py  # FFmpeg: probe, thumbnails, frame extract
│   │   ├── upload_service.py# Chunked upload assembly
│   │   ├── timeline_service.py # Rough-cut generation
│   │   └── otio_exporter.py # OpenTimelineIO → XML / EDL
│   ├── ai/
│   │   ├── cv_analyser.py   # OpenCV: blur, shake, exposure, pHash
│   │   ├── scene_detector.py# PySceneDetect wrapper
│   │   ├── transcriber.py   # Whisper local transcription
│   │   └── llm_scorer.py    # LLM tagging (structured metadata only)
│   └── workers/
│       ├── celery_app.py    # Celery factory + routing
│       ├── analysis_tasks.py# Per-clip + project analysis tasks
│       └── export_tasks.py  # OTIO export task
├── tests/
│   ├── conftest.py
│   ├── test_projects.py
│   └── test_cv_analyser.py
├── alembic/
│   └── env.py
├── storage/                 # Auto-created at runtime
│   ├── uploads/
│   ├── thumbnails/
│   ├── exports/
│   ├── temp/
│   └── db/
├── main.py                  # Uvicorn entry point
├── celery_worker.py         # Celery entry point
├── example_client.py        # End-to-end demo script
├── start_dev.bat            # Windows 1-click launcher
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## Quick Start (Windows — No Docker)

### Prerequisites
- **Python 3.11+** — https://www.python.org/downloads/
- **FFmpeg** — https://ffmpeg.org/download.html → add to PATH
- **Redis for Windows** — install one of these options:

  **Option A — Memurai (native Windows Redis-compatible server, recommended):**
  ```
  https://www.memurai.com/get-memurai   ← free for development
  ```
  After install, Memurai runs as a Windows service automatically on port 6379.

  **Option B — Redis via WSL (Windows Subsystem for Linux):**
  ```powershell
  # In WSL terminal:
  sudo apt update && sudo apt install redis-server
  redis-server
  ```

  **Option C — Portable Redis for Windows:**
  ```
  https://github.com/microsoftarchive/redis/releases
  ```
  Run `redis-server.exe` from the extracted folder.

### Setup

```powershell
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env — set OPENAI_API_KEY if you want LLM tagging
# Make sure Redis is running on localhost:6379

# 4. Start everything with one command
start_dev.bat
```

`start_dev.bat` opens 3 terminal windows:
- **Terminal 1** — FastAPI server on port 8000
- **Terminal 2** — Celery analysis worker (4 concurrent)
- **Terminal 3** — Celery export worker (2 concurrent)

Or start each manually in separate terminals:
```powershell
# Terminal 1
python main.py

# Terminal 2 (Windows: add -P threads)
celery -A celery_worker.celery_app worker --loglevel=info -Q analysis,default -P threads -c 4

# Terminal 3 (Windows: add -P threads)
celery -A celery_worker.celery_app worker --loglevel=info -Q export -P threads -c 2
```

> [!NOTE]
> On Windows, running Celery workers with the default prefork pool can fail with `PermissionError: [WinError 5] Access is denied` due to OS-level multiprocessing restrictions. Using `-P threads` avoids this and runs the worker tasks inside a thread pool.

### API Docs
Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health**: http://localhost:8000/health

---

## API Reference

### Projects
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/projects/` | Create project |
| `GET` | `/api/v1/projects/` | List all projects |
| `GET` | `/api/v1/projects/{id}` | Get project |
| `PATCH` | `/api/v1/projects/{id}` | Update project |
| `DELETE` | `/api/v1/projects/{id}` | Delete project |

### Clips (Upload)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/clips/upload/init` | Init chunked upload session |
| `POST` | `/api/v1/clips/{id}/chunk/{n}` | Upload chunk N (binary body) |
| `POST` | `/api/v1/clips/upload/simple` | Single-shot upload (≤ ~1GB) |
| `GET` | `/api/v1/clips/project/{pid}` | List clips in project |
| `GET` | `/api/v1/clips/{id}` | Get clip detail |
| `DELETE` | `/api/v1/clips/{id}` | Delete clip |

### Analysis
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analysis/clip/{id}/start` | Queue analysis for clip |
| `POST` | `/api/v1/analysis/project/{pid}/start` | Queue analysis for all clips |
| `GET` | `/api/v1/analysis/task/{task_id}/status` | Poll Celery task |
| `GET` | `/api/v1/analysis/clip/{id}` | Get full analysis result |
| `GET` | `/api/v1/analysis/project/{pid}/scores` | Get all clip scores |
| `POST` | `/api/v1/analysis/project/{pid}/duplicates` | Detect duplicate clips |

### Timelines & Export
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/timelines/generate` | Generate rough-cut timeline |
| `GET` | `/api/v1/timelines/{id}` | Get timeline |
| `GET` | `/api/v1/timelines/project/{pid}` | List timelines |
| `POST` | `/api/v1/timelines/{id}/export/xml` | Export Premiere XML (async) |
| `POST` | `/api/v1/timelines/{id}/export/edl` | Export EDL (async) |
| `POST` | `/api/v1/timelines/{id}/export/all` | Export all formats |
| `GET` | `/api/v1/timelines/{id}/download/{fmt}` | Download file (xml/edl/otio) |

---

## Analysis Pipeline (per clip)

```
Clip uploaded
    │
    ▼
[Celery task: analyse_clip]
    │
    ├─► CV Analysis (OpenCV)
    │     • Blur score     (Laplacian variance)
    │     • Shake score    (Farneback optical flow)
    │     • Exposure score (luminance histogram)
    │     • Perceptual hash (dHash, 16x16)
    │     • Usable ranges   (frame-by-frame quality windows)
    │
    ├─► Scene Detection (PySceneDetect)
    │     • ContentDetector (configurable threshold)
    │     • Returns [{scene_number, start_time, end_time}]
    │
    ├─► Transcription (Whisper — LOCAL, no API calls)
    │     • Audio extracted to 16kHz mono WAV
    │     • Model: configurable (tiny→large)
    │     • Returns full text + timestamped segments
    │
    └─► LLM Tagging (OpenAI — STRUCTURED METADATA ONLY)
          • Input: duration, resolution, scores, transcript excerpt
          • NO raw video or frames sent
          • Output: tags[], summary
          • Falls back to rule-based if no API key
```

## Example Analysis Output

```json
{
  "clip_id": "a3b7c921-...",
  "score": 8.7,
  "usable_ranges": [
    {"start": 12.4, "end": 24.8}
  ],
  "tags": ["walking", "outdoor", "stable"],
  "summary": "Person walking outside during golden hour, stable footage"
}
```

---

## Chunked Upload (for 4K files)

```python
import requests, math, os

FILE = "raw_4k_clip.mp4"
CHUNK_MB = 10
BASE = "http://localhost:8000/api/v1"

file_size = os.path.getsize(FILE)
chunk_size = CHUNK_MB * 1024 * 1024
total_chunks = math.ceil(file_size / chunk_size)

# Init session
r = requests.post(f"{BASE}/clips/upload/init", json={
    "project_id": "<pid>",
    "filename": FILE,
    "file_size": file_size,
    "total_chunks": total_chunks
})
clip_id = r.json()["id"]

# Upload chunks
with open(FILE, "rb") as f:
    for i in range(total_chunks):
        chunk = f.read(chunk_size)
        requests.post(
            f"{BASE}/clips/{clip_id}/chunk/{i}",
            data=chunk,
            headers={"Content-Type": "application/octet-stream"}
        )
```
Resumable: if upload fails, re-send only missing chunks. The server auto-assembles when all chunks arrive.

---

## Configuration

Key `.env` settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `base` | `tiny/base/small/medium/large` |
| `OPENAI_API_KEY` | — | Leave empty to use rule-based tagging |
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM model for tagging/sequencing |
| `CELERY_CONCURRENCY` | `4` | Parallel analysis workers |
| `MAX_UPLOAD_SIZE_GB` | `20` | Per-file upload limit |
| `CHUNK_SIZE_MB` | `10` | Suggested client-side chunk size |

---

## Database Migrations

```powershell
# Create migration
alembic revision --autogenerate -m "add new field"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Running Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

---

## Scaling to Production

1. **Database**: Replace SQLite URL with PostgreSQL (`postgresql+asyncpg://...`)
2. **Storage**: Swap `upload_dir` for S3/GCS — modify `upload_service.py`
3. **GPU Whisper**: Set `WHISPER_MODEL=large` + run workers on GPU node
4. **Worker scaling**: `docker-compose scale worker_analysis=8`
5. **Celery beat**: Add scheduled duplicate detection sweeps

---

## Security Notes

- Set `DEBUG=false` in production
- Replace `SECRET_KEY` with a cryptographically random value
- Restrict CORS origins in `main.py`
- Add authentication middleware (JWT/API key) before deploying
