#!/bin/bash
set -euo pipefail

# Palantir C2 v2 — Unified Launcher
# Starts the FastAPI backend, Cesium dashboard, and (optionally) drone simulator.
# Usage: ./palantir.sh [--no-sim] [--no-browser]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse flags
NO_SIM=false
NO_BROWSER=false
DEMO_MODE=false
for arg in "$@"; do
    case "$arg" in
        --no-sim)     NO_SIM=true ;;
        --no-browser) NO_BROWSER=true ;;
        --demo)       DEMO_MODE=true ;;
        --help|-h)
            echo "Usage: ./palantir.sh [--no-sim] [--no-browser] [--demo]"
            echo "  --no-sim      Skip drone video simulator (useful if OpenCV not installed)"
            echo "  --no-browser  Don't auto-open browser"
            echo "  --demo        Enable auto-pilot demo mode (full F2T2EA kill chain)"
            exit 0
            ;;
        *) echo "Unknown flag: $arg (try --help)"; exit 1 ;;
    esac
done

# Export demo mode for the backend
if [ "$DEMO_MODE" = true ]; then
    export DEMO_MODE=true
fi

echo "================================================"
if [ "$DEMO_MODE" = true ]; then
    echo "   PALANTIR C2 — DEMO MODE (AUTO-PILOT)"
else
    echo "   PALANTIR C2 — MISSION CONTROL SYSTEM v2"
fi
echo "================================================"
echo ""

# Preflight checks
if [ ! -d "./venv" ]; then
    echo "ERROR: Python venv not found."
    echo "  Run: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "./src/python/api_main.py" ]; then
    echo "ERROR: api_main.py not found. Are you in the project root?"
    exit 1
fi

# Kill stale processes on our ports
for PORT in 8000 3000; do
    STALE_PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$STALE_PID" ]; then
        echo "Killing stale process on port $PORT (PID $STALE_PID)..."
        kill $STALE_PID 2>/dev/null || true
        sleep 1
    fi
done

# Kill child processes on exit
PIDS=()
cleanup() {
    echo ""
    echo "Shutting down Palantir C2..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    echo "All systems offline."
}
trap cleanup EXIT INT TERM

# 1. Start API Backend
echo "[1/3] Starting FastAPI backend on :8000..."
./venv/bin/python3 src/python/api_main.py &
PIDS+=($!)
BACKEND_PID=$!

echo "      Waiting for backend..."
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/api/theaters > /dev/null 2>&1; then
        echo "      Backend ready."
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "      WARNING: Backend may not be ready yet (continuing anyway)."
    fi
    sleep 1
done

# 2. Start Dashboard HTTP Server
echo "[2/3] Starting Cesium dashboard on :3000..."
(cd src/frontend && python3 -m http.server 3000 > /dev/null 2>&1) &
PIDS+=($!)
sleep 1

# 3. Open Browser
if [ "$NO_BROWSER" = false ]; then
    echo "[3/3] Opening browser..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open http://localhost:3000
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open http://localhost:3000 2>/dev/null || true
    fi
else
    echo "[3/3] Skipping browser (--no-browser)."
fi

echo ""
echo "================================================"
echo "  Backend:   http://localhost:8000"
echo "  Dashboard: http://localhost:3000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  WebSocket: ws://localhost:8000/ws"
echo "================================================"
echo ""
echo "Press Ctrl+C to shut down all services."
echo ""

# 4. Start Drone Simulator (optional — requires OpenCV)
if [ "$NO_SIM" = false ]; then
    if ./venv/bin/python3 -c "import cv2" 2>/dev/null; then
        echo "Starting drone simulator..."
        ./venv/bin/python3 src/python/vision/video_simulator.py &
        PIDS+=($!)
    else
        echo "NOTE: Drone simulator skipped (OpenCV not installed)."
        echo "      Install with: ./venv/bin/pip install opencv-python-headless"
    fi
else
    echo "Drone simulator skipped (--no-sim)."
fi

# Keep script alive until backend exits
wait $BACKEND_PID
