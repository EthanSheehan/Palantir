import subprocess
import threading
import time
import os
import sys
import socket
import atexit
import signal
import urllib.request
import urllib.error

BACKEND_PORT = 8012
FRONTEND_PORT = 8093
HEALTH_URL = f"http://localhost:{BACKEND_PORT}/health"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"
BACKEND_TIMEOUT = 15  # seconds
FRONTEND_TIMEOUT = 5  # seconds
POLL_INTERVAL = 0.2   # seconds

_procs = []  # track subprocesses for cleanup


def _cleanup():
    """Terminate all child processes (and their entire process trees)."""
    for proc in _procs:
        if proc.poll() is None:
            if sys.platform == 'win32':
                # taskkill /T kills the full process tree (including uvicorn reload workers)
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                    capture_output=True,
                )
            else:
                proc.terminate()
    for proc in _procs:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


atexit.register(_cleanup)


def _signal_handler(signum, frame):
    print("\nInterrupted — shutting down...")
    _cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def _port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def _wait_for_health(url, timeout, proc):
    """Poll a URL until it returns 200 or timeout is reached."""
    start = time.time()
    while time.time() - start < timeout:
        # Check if process died
        if proc.poll() is not None:
            return False
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            if resp.status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(POLL_INTERVAL)
    return False


def _drain_pipe(pipe):
    """Continuously read and discard pipe output to prevent buffer deadlock."""
    try:
        while pipe.read(4096):
            pass
    except (OSError, ValueError):
        pass


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")

    print("========================================")
    print("       Starting Grid 11 System...       ")
    print("========================================")

    # ── Pre-flight: check ports ──
    if _port_in_use(BACKEND_PORT):
        print(f"[ERROR] Port {BACKEND_PORT} is already in use. Kill the existing process and retry.")
        sys.exit(1)
    if _port_in_use(FRONTEND_PORT):
        print(f"[ERROR] Port {FRONTEND_PORT} is already in use. Kill the existing process and retry.")
        sys.exit(1)

    # ── 1. Start backend ──
    print(f"[1/4] Starting Backend (FastAPI on port {BACKEND_PORT})...")
    backend_proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    _procs.append(backend_proc)

    # ── 2. Wait for backend health ──
    print(f"[2/4] Waiting for backend to be ready (up to {BACKEND_TIMEOUT}s)...")
    if _wait_for_health(HEALTH_URL, BACKEND_TIMEOUT, backend_proc):
        print("       Backend is healthy!")
        threading.Thread(target=_drain_pipe, args=(backend_proc.stdout,), daemon=True).start()
    else:
        if backend_proc.poll() is not None:
            # Process exited — dump output for diagnostics
            output = backend_proc.stdout.read().decode(errors="replace") if backend_proc.stdout else ""
            print(f"[ERROR] Backend process exited with code {backend_proc.returncode}")
            if output:
                print("--- Backend output ---")
                print(output[-2000:])  # last 2000 chars
                print("--- End ---")
        else:
            print(f"[ERROR] Backend did not become healthy within {BACKEND_TIMEOUT}s")
            backend_proc.terminate()
        sys.exit(1)

    # ── 3. Start frontend (Vite dev server) ──
    print(f"[3/4] Starting Frontend (Vite on port {FRONTEND_PORT})...")
    # Check if node_modules exists; if not, run npm install
    node_modules = os.path.join(frontend_dir, "node_modules")
    if not os.path.isdir(node_modules):
        print("       Installing npm dependencies...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    vite_bin = os.path.join(frontend_dir, "node_modules", "vite", "bin", "vite.js")
    frontend_proc = subprocess.Popen(
        ["node", vite_bin, "--port", str(FRONTEND_PORT)],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    _procs.append(frontend_proc)

    if _wait_for_health(FRONTEND_URL, FRONTEND_TIMEOUT + 10, frontend_proc):
        print("       Frontend (Vite) is serving!")
        threading.Thread(target=_drain_pipe, args=(frontend_proc.stdout,), daemon=True).start()
    else:
        print(f"[ERROR] Frontend did not start within {FRONTEND_TIMEOUT}s")
        sys.exit(1)

    # ── 4. Launch desktop window ──
    print("[4/4] Launching Grid 11 Desktop App...")
    print("========================================")

    from PyQt5.QtCore import QUrl, QTimer
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile

    app = QApplication(sys.argv)

    # Clear cache so it always loads the latest code
    profile = QWebEngineProfile.defaultProfile()
    profile.setHttpCacheType(QWebEngineProfile.NoCache)

    window = QMainWindow()
    window.setWindowTitle("AMS V0.2")
    window.resize(1600, 900)

    class _WebView(QWebEngineView):
        def contextMenuEvent(self, event):
            event.ignore()  # suppress browser right-click menu; handled by Cesium

    webview = _WebView()
    webview.setUrl(QUrl(FRONTEND_URL))

    window.setCentralWidget(webview)
    window.show()

    # Periodically check if subprocesses are still alive
    def _check_procs():
        if backend_proc.poll() is not None:
            print("[WARNING] Backend process has exited unexpectedly!")
        if frontend_proc.poll() is not None:
            print("[WARNING] Frontend process has exited unexpectedly!")

    health_timer = QTimer()
    health_timer.timeout.connect(_check_procs)
    health_timer.start(5000)  # check every 5 seconds

    app.exec_()

    print("\nShutting down Grid 11 servers...")
    _cleanup()
    print("Shutdown complete. Goodbye!")


if __name__ == "__main__":
    main()
