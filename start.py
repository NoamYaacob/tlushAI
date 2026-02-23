#!/usr/bin/env python3
"""Launch backend and frontend dev servers simultaneously.

Usage:
    python start.py

Press Ctrl+C to stop both servers.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

processes: list[subprocess.Popen] = []


def cleanup(signum=None, frame=None):
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    env = os.environ.copy()

    backend = subprocess.Popen(
        ["uvicorn", "app.main:app", "--port", "8000", "--reload"],
        cwd=BACKEND_DIR,
        env=env,
    )
    processes.append(backend)

    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND_DIR,
        env=env,
    )
    processes.append(frontend)

    print(f"Backend  → http://localhost:8000  (pid {backend.pid})")
    print(f"Frontend → http://localhost:5173  (pid {frontend.pid})")
    print("Press Ctrl+C to stop both.\n")

    try:
        # Wait for either process to exit
        while True:
            for proc in processes:
                ret = proc.poll()
                if ret is not None:
                    name = "Backend" if proc is backend else "Frontend"
                    print(f"\n{name} exited with code {ret}. Stopping...")
                    cleanup()
            # Avoid busy-loop
            try:
                backend.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
