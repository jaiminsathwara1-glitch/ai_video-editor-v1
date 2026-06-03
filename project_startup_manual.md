# AI Video Rough-Cut Platform: Startup & Operation Manual

This guide describes how to start and verify all components of the system on Windows.

---

## 📋 System Prerequisites

Before starting, ensure you have:
1. **Redis Server** running on localhost port `6379`.
2. **FFmpeg & FFprobe** installed and available in your system path (or configured in `.env`).
3. **Python 3.11+** installed with the virtual environment activated (`venv`).
4. **Node.js & npm** installed for the frontend web application.

---

## ⚡ Option A: Unified Single-Script Start (Recommended)

You can launch all 4 components (FastAPI backend, Celery analysis worker, Celery export worker, and Vite React frontend) concurrently in a single terminal with colored logging and automatic dependency check/cleanup:

1. Open a Command Prompt or PowerShell in the root directory: `e:\ai-video_editing`.
2. Run the orchestrator script using your virtual environment Python:
   ```powershell
   .\venv\Scripts\python run_project.py
   ```
3. To stop all services gracefully at any time, simply press `Ctrl+C` in that terminal.

---

## 🚀 Option B: Multi-Window Automated Start

To launch the backend and the two workers in separate command windows automatically (without merging logs):

1. Open a Command Prompt or PowerShell in the root directory: `e:\ai-video_editing`.
2. Run the startup script:
   ```cmd
   .\start_dev.bat
   ```
3. Open a second terminal window to start the frontend:
   ```powershell
   cd frontend
   npm run dev
   ```

---

## 🛠️ Option C: Manual Step-by-Step Launch

If you prefer to start each service manually to watch their individual logs, open **four separate terminals** and run the following:

### 1. Start the FastAPI Web Server
Run the Uvicorn web server in your first terminal:
```powershell
# Navigate to the project root
cd e:\ai-video_editing
# Activate your python virtual environment
.\venv\Scripts\activate
# Start the backend application
python main.py
```
* **URL:** [http://localhost:8000](http://localhost:8000)
* **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Start the Celery Analysis Worker
Run the worker handling computer vision, scene detection, whisper, and LLM processing in your second terminal:
```powershell
cd e:\ai-video_editing
.\venv\Scripts\activate
celery -A celery_worker.celery_app worker --loglevel=info -Q analysis,default -P threads -c 1 -n analysis@%h
```

### 3. Start the Celery Export Worker
Run the worker handling rendering, timelines, XML, and EDL exports in your third terminal:
```powershell
cd e:\ai-video_editing
.\venv\Scripts\activate
celery -A celery_worker.celery_app worker --loglevel=info -Q export -P threads -c 2 -n export@%h
```

### 4. Start the React Frontend Web App
Run the Vite development server in your fourth terminal:
```powershell
cd e:\ai-video_editing\frontend
npm run dev
```
* **URL:** [http://localhost:5173](http://localhost:5173)

---

## 🔍 Verifying the System Status

Once everything is started, you can verify that all systems are healthy by calling the API health check.

Run this command in any terminal:
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/health/workers" | Select-Object -ExpandProperty Content
```

**Expected JSON Response:**
```json
{
  "status": "ok",
  "analysis_worker_online": true,
  "export_worker_online": true,
  "workers": [
    { "name": "analysis@DESKTOP-XXX", "queues": ["analysis", "default"] },
    { "name": "export@DESKTOP-XXX", "queues": ["export"] }
  ],
  "warning": null
}
```
If `"analysis_worker_online"` or `"export_worker_online"` is `false`, check the corresponding worker terminal for errors.
