"""Run the private FastAPI backend and public Streamlit UI in one Render service."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
API_URL = "http://127.0.0.1:8000"


def wait_for_api(process: subprocess.Popen, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("FastAPI exited before becoming ready")
        try:
            with urlopen(f"{API_URL}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.5)
    raise RuntimeError("FastAPI startup timed out")


def main() -> int:
    children: list[subprocess.Popen] = []
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    env = os.environ.copy()
    env["API_BASE_URL"] = API_URL
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
    try:
        api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app",
             "--host", "127.0.0.1", "--port", "8000", "--workers", "1"],
            cwd=ROOT, env=env,
        )
        children.append(api)
        wait_for_api(api)
        if stopping:
            return 0
        ui = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py",
             f"--server.port={env.get('PORT', '10000')}",
             "--server.address=0.0.0.0", "--server.headless=true",
             "--browser.gatherUsageStats=false"],
            cwd=ROOT, env=env,
        )
        children.append(ui)
        print("FastAPI ready; Streamlit starting on the public port", flush=True)
        while not stopping:
            if any(child.poll() is not None for child in children):
                print("A server exited; shutting down the service", flush=True)
                return 1
            time.sleep(0.5)
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
