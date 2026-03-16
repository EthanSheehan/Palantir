#!/bin/bash

# Palantir C2 - Unified Launcher
# This script starts the Backend, the Dashboard, and the Drone Simulator.

echo "------------------------------------------------"
echo "   🛡️  PALANTIR C2 - MISSION CONTROL SYSTEM  🛡️"
echo "------------------------------------------------"

# Kill existing processes on exit
trap 'kill $(jobs -p)' EXIT

# 1. Start API Backend
echo "📡 Starting Backend API..."
./venv/bin/python3 src/python/api_main.py &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 3

# 2. Start Dashboard HTTP Server
echo "🖥️  Starting Dashboard on http://localhost:3000..."
(cd src/frontend && python3 -m http.server 3000 > /dev/null 2>&1) &
sleep 1

# 3. Open Browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:3000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:3000
fi

# 4. Start Drone Simulator
echo "🤖 Starting Drone Simulator (Ready for Mission Control)..."
./venv/bin/python3 src/python/vision/video_simulator.py

# Wait for simulator to stay alive
wait $!
