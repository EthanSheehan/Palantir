#!/bin/bash
set -euo pipefail

# Palantir C2 v2 — Unified Launcher
# Starts the FastAPI backend, Cesium dashboard, and drone simulator.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "   PALANTIR C2 — MISSION CONTROL SYSTEM v2"
echo "================================================"
echo ""

# Preflight checks
if [ ! -d "./venv" ]; then
    echo "ERROR: Python venv not found. Run: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "./src/python/api_main.py" ]; then
    echo "ERROR: api_main.py not found. Are you in the project root?"
    exit 1
fi

# Kill child processes on exit
cleanup() {
    echo ""
    echo "Shutting down Palantir C2..."
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    echo "All systems offline."
}
trap cleanup EXIT INT TERM

# 1. Start API Backend
echo "[1/3] Starting FastAPI backend on :8000..."
./venv/bin/python3 src/python/api_main.py &
BACKEND_PID=$!

# Wait for backend to be ready
echo "      Waiting for backend..."
for i in $(seq 1 10); do
    if curl -s http://localhost:8000/api/theaters > /dev/null 2>&1; then
        echo "      Backend ready."
        break
    fi
    if [ $i -eq 10 ]; then
        echo "      WARNING: Backend may not be ready yet."
    fi
    sleep 1
done

# 2. Start Dashboard HTTP Server
echo "[2/3] Starting Cesium dashboard on :3000..."
(cd src/frontend && python3 -m http.server 3000 > /dev/null 2>&1) &
DASHBOARD_PID=$!
sleep 1

# 3. Open Browser
echo "[3/3] Opening browser..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:3000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:3000 2>/dev/null || true
fi

echo ""
echo "================================================"
echo "  Backend:   http://localhost:8000"
echo "  Dashboard: http://localhost:3000"
echo "  API Docs:  http://localhost:8000/docs"
echo "================================================"
echo ""
echo "Press Ctrl+C to shut down all services."
echo ""

# 4. Start Drone Simulator (foreground — keeps script alive)
echo "Starting drone simulator..."
./venv/bin/python3 src/python/vision/video_simulator.py || true

# If simulator exits, keep backend alive
wait $BACKEND_PID
