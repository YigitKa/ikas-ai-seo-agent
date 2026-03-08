#!/usr/bin/env python3
"""
Cross-platform launcher for ikas AI SEO Agent.
Works on Windows, macOS, and Linux.

Usage:
    python start.py          # production: build frontend + start backend
    python start.py dev      # backend :8000 + Vite :5173 in parallel
    python start.py build    # build frontend only
    python start.py backend  # start backend only
"""

import os
import signal
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
DIST_DIR = os.path.join(WEB_DIR, "dist")

IS_WINDOWS = sys.platform == "win32"
NPM = "npm.cmd" if IS_WINDOWS else "npm"

_processes: list[subprocess.Popen] = []
_shutdown = threading.Event()


def _stream(proc: subprocess.Popen, prefix: str) -> None:
    """Stream stdout/stderr of a process with a prefix to the terminal."""
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            if _shutdown.is_set():
                break
            sys.stdout.write(f"[{prefix}] {line}")
            sys.stdout.flush()
    except Exception:
        pass


def _run(cmd: list[str], cwd: str | None = None, check: bool = True) -> int:
    """Run a command synchronously, streaming output. Returns exit code."""
    proc = subprocess.run(cmd, cwd=cwd)
    if check and proc.returncode != 0:
        print(f"\n[start.py] Command failed: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.returncode


def _start(cmd: list[str], prefix: str, cwd: str | None = None) -> subprocess.Popen:
    """Start a process and stream its output in a background thread."""
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    _processes.append(proc)
    t = threading.Thread(target=_stream, args=(proc, prefix), daemon=True)
    t.start()
    return proc


def _shutdown_all(signum=None, frame=None) -> None:  # noqa: ARG001
    if _shutdown.is_set():
        return
    _shutdown.set()
    print("\n[start.py] Shutting down...", flush=True)
    for proc in _processes:
        try:
            if proc.poll() is None:
                if IS_WINDOWS:
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGTERM)
        except Exception:
            pass
    for proc in _processes:
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    sys.exit(0)


def install_python_deps() -> None:
    req = os.path.join(ROOT, "requirements.txt")
    if os.path.exists(req):
        print("[start.py] Installing Python dependencies...")
        _run([sys.executable, "-m", "pip", "install", "-r", req, "-q"])


def install_node_deps() -> None:
    node_modules = os.path.join(WEB_DIR, "node_modules")
    if not os.path.exists(node_modules):
        print("[start.py] Installing Node dependencies...")
        _run([NPM, "install"], cwd=WEB_DIR)


def build_frontend() -> None:
    print("[start.py] Building frontend...")
    _run([NPM, "run", "build"], cwd=WEB_DIR)
    print("[start.py] Frontend built.")


def start_backend() -> subprocess.Popen:
    return _start(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"],
        prefix="backend",
        cwd=ROOT,
    )


def start_frontend_dev() -> subprocess.Popen:
    return _start([NPM, "run", "dev"], prefix="frontend", cwd=WEB_DIR)


def mode_dev() -> None:
    install_python_deps()
    install_node_deps()

    signal.signal(signal.SIGINT, _shutdown_all)
    if not IS_WINDOWS:
        signal.signal(signal.SIGTERM, _shutdown_all)

    print("[start.py] Starting backend on :8000 and frontend dev server on :5173 ...")
    start_backend()
    start_frontend_dev()

    print("[start.py] Both services running. Press Ctrl+C to stop.")
    try:
        _shutdown.wait()
    except KeyboardInterrupt:
        _shutdown_all()


def mode_build() -> None:
    install_node_deps()
    build_frontend()


def mode_backend() -> None:
    install_python_deps()

    signal.signal(signal.SIGINT, _shutdown_all)
    if not IS_WINDOWS:
        signal.signal(signal.SIGTERM, _shutdown_all)

    print("[start.py] Starting backend on :8000 ...")
    start_backend()

    try:
        _shutdown.wait()
    except KeyboardInterrupt:
        _shutdown_all()


def mode_prod() -> None:
    install_python_deps()
    install_node_deps()

    if not os.path.exists(DIST_DIR):
        build_frontend()

    signal.signal(signal.SIGINT, _shutdown_all)
    if not IS_WINDOWS:
        signal.signal(signal.SIGTERM, _shutdown_all)

    print("[start.py] Starting production server on http://localhost:8000 ...")
    start_backend()

    print("[start.py] Server running. Press Ctrl+C to stop.")
    try:
        _shutdown.wait()
    except KeyboardInterrupt:
        _shutdown_all()


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "prod"

    if mode == "dev":
        mode_dev()
    elif mode == "build":
        mode_build()
    elif mode == "backend":
        mode_backend()
    elif mode in ("prod", "production"):
        mode_prod()
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        print("Usage: python start.py [dev|build|backend|prod]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
