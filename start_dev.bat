@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  start_dev.bat  —  Start all services for local development (Windows)
REM
REM  Prerequisites:
REM    1. Python 3.11+ in PATH
REM    2. Redis running (use WSL or Redis for Windows)
REM    3. FFmpeg in PATH
REM    4. Run: pip install -r requirements.txt
REM    5. Copy .env.example to .env and fill in values
REM ─────────────────────────────────────────────────────────────────────────

echo [1/3] Starting FastAPI server...
start "FastAPI" cmd /k "python main.py"

timeout /t 2 /nobreak >nul

echo [2/3] Starting Celery analysis worker...
start "Celery-Analysis" cmd /k "celery -A celery_worker.celery_app worker --loglevel=info -Q analysis,default -P threads -c 1 -n analysis@%%h"

timeout /t 2 /nobreak >nul

echo [3/3] Starting Celery export worker...
start "Celery-Export" cmd /k "celery -A celery_worker.celery_app worker --loglevel=info -Q export -P threads -c 2 -n export@%%h"

echo.
echo All services started!
echo    API:     http://localhost:8000
echo    Docs:    http://localhost:8000/docs
echo    Health:  http://localhost:8000/health
echo    Workers: http://localhost:8000/health/workers
