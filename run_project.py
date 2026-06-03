#!/usr/bin/env python
import os
import sys
import subprocess
import threading
import socket
import time
import signal
from pathlib import Path

# Enable ANSI escape sequences on Windows
if sys.platform == "win32":
    os.system("")

# Color definitions
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

PREFIX_COLORS = {
    "System": BOLD + WHITE,
    "Backend": GREEN,
    "Analysis": CYAN,
    "Export": MAGENTA,
    "Frontend": YELLOW,
}

def log(service, message):
    color = PREFIX_COLORS.get(service, RESET)
    # Print each line with the prefix
    for line in message.rstrip().split("\n"):
        print(f"{color}[{service}]{RESET} {line}")

def check_redis(host="localhost", port=6379):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def kill_process_tree(pid):
    """Gracefully but forcefully terminate a process and all its children."""
    if sys.platform == "win32":
        try:
            # Taskkill /T kills the process tree, /F forces it
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        except Exception:
            pass
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

def read_stream(service_name, stream, shutdown_event):
    """Reads lines from a subprocess stream and logs them with service prefix."""
    try:
        # Use a non-blocking/iterator read
        for line in iter(stream.readline, ""):
            if shutdown_event.is_set():
                break
            if line:
                log(service_name, line)
    except Exception as e:
        if not shutdown_event.is_set():
            log("System", f"Error reading stream from {service_name}: {e}")
    finally:
        try:
            stream.close()
        except Exception:
            pass

def main():
    workspace_dir = Path(__file__).parent.resolve()
    os.chdir(workspace_dir)

    print(BOLD + GREEN + "=============================================" + RESET)
    print(BOLD + GREEN + "  AI Video Rough-Cut Platform Orchestrator   " + RESET)
    print(BOLD + GREEN + "=============================================" + RESET)

    # 1. Check Redis
    log("System", "Checking Redis connectivity...")
    if not check_redis():
        log("System", RED + "ERROR: Redis is not running on localhost:6379." + RESET)
        log("System", RED + "Please start Redis before running the project." + RESET)
        sys.exit(1)
    log("System", GREEN + "Redis is running." + RESET)

    # 2. Check Python Venv
    is_windows = sys.platform == "win32"
    venv_dir = workspace_dir / "venv"
    if is_windows:
        python_exe = venv_dir / "Scripts" / "python.exe"
        celery_exe = venv_dir / "Scripts" / "celery.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
        celery_exe = venv_dir / "bin" / "celery"

    if not python_exe.exists():
        log("System", RED + f"ERROR: Virtual environment not found at {venv_dir}." + RESET)
        log("System", RED + "Please run your setup commands to initialize the virtualenv." + RESET)
        sys.exit(1)

    # 3. Check Frontend node_modules
    frontend_dir = workspace_dir / "frontend"
    node_modules_dir = frontend_dir / "node_modules"
    if not node_modules_dir.exists():
        log("System", YELLOW + "node_modules not found in frontend directory. Running npm install..." + RESET)
        try:
            subprocess.run(
                ["npm", "install"],
                cwd=frontend_dir,
                shell=True,
                check=True
            )
            log("System", GREEN + "npm install completed successfully." + RESET)
        except subprocess.CalledProcessError as e:
            log("System", RED + f"ERROR: npm install failed: {e}. Please run 'npm install' in the frontend folder." + RESET)
            sys.exit(1)

    # Add venv Scripts to Path (needed for workers)
    env = os.environ.copy()
    if is_windows:
        venv_scripts = str(venv_dir / "Scripts")
        if venv_scripts not in env.get("PATH", ""):
            env["PATH"] = venv_scripts + os.pathsep + env.get("PATH", "")

    # Define the services
    services_config = [
        {
            "name": "Backend",
            "cmd": [str(python_exe), "main.py"],
            "cwd": workspace_dir,
        },
        {
            "name": "Analysis",
            "cmd": [
                str(celery_exe),
                "-A",
                "celery_worker.celery_app",
                "worker",
                "--loglevel=info",
                "-Q",
                "analysis,default",
                "-P",
                "threads",
                "-c",
                "1",
                "-n",
                "analysis@%h" if is_windows else "analysis@localhost"
            ],
            "cwd": workspace_dir,
        },
        {
            "name": "Export",
            "cmd": [
                str(celery_exe),
                "-A",
                "celery_worker.celery_app",
                "worker",
                "--loglevel=info",
                "-Q",
                "export",
                "-P",
                "threads",
                "-c",
                "2",
                "-n",
                "export@%h" if is_windows else "export@localhost"
            ],
            "cwd": workspace_dir,
        },
        {
            "name": "Frontend",
            "cmd": ["npm", "run", "dev"],
            "cwd": frontend_dir,
        }
    ]

    processes = []
    threads = []
    shutdown_event = threading.Event()

    # Define signal handler for graceful shutdown
    def shutdown_handler(signum, frame):
        if shutdown_event.is_set():
            return
        log("System", "\n" + YELLOW + "Shutdown signal received. Cleaning up all services..." + RESET)
        shutdown_event.set()

        # Terminate all processes
        for p_name, proc in processes:
            log("System", f"Stopping service: {p_name} (PID: {proc.pid})...")
            kill_process_tree(proc.pid)

        log("System", GREEN + "All services stopped successfully." + RESET)
        sys.exit(0)

    # Register signals
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        log("System", "Starting all services...")
        for cfg in services_config:
            name = cfg["name"]
            cmd = cfg["cmd"]
            cwd = cfg["cwd"]

            log("System", f"Starting {name}: {' '.join(cmd)}")
            
            # Start process
            # Use shell=True for frontend (npm) to resolve execution path correctly,
            # and on Windows for CLI commands.
            use_shell = (name == "Frontend" or is_windows)
            
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,                 # Line buffered
                shell=use_shell,
                env=env,
                # On Windows, use CREATE_NEW_PROCESS_GROUP to allow signal handling if needed,
                # but taskkill handles it fine. On Unix, we might want start_new_session.
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if is_windows else 0
            )
            processes.append((name, proc))

            # Start thread to read output
            t = threading.Thread(
                target=read_stream,
                args=(name, proc.stdout, shutdown_event),
                daemon=True
            )
            t.start()
            threads.append(t)
            
            # Brief delay to allow port binding and stagger startups
            time.sleep(1.5)

        log("System", GREEN + BOLD + "All services are up and running! Press Ctrl+C to stop." + RESET)
        log("System", "  FastAPI Backend: http://localhost:8000")
        log("System", "  API docs:        http://localhost:8000/docs")
        log("System", "  React Frontend:  http://localhost:5173")

        # Keep main thread alive and monitor processes
        while not shutdown_event.is_set():
            for name, proc in processes:
                # Check if process has terminated unexpectedly
                ret_code = proc.poll()
                if ret_code is not None:
                    log("System", RED + f"CRITICAL: Service '{name}' exited unexpectedly with code {ret_code}!" + RESET)
                    # Trigger shutdown of all other services
                    shutdown_handler(None, None)
            time.sleep(1)

    except KeyboardInterrupt:
        shutdown_handler(None, None)

if __name__ == "__main__":
    main()
