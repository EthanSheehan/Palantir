#!/bin/bash
# Project Antigravity Startup Script

echo "🚀 Starting Project Antigravity C2 System..."

# 0. Clean up existing processes on target ports
echo "🧹 Cleaning up existing processes on ports 3000 and 8000..."
lsof -ti:3000,8000 | xargs kill -9 2>/dev/null

# Kill any existing background processes on exit
trap "kill 0" EXIT

# 1. Start the API Backend
echo "📡 Starting API Backend..."
python3 src/python/api_main.py &

# 2. Start the Drone Simulator
echo "🚁 Starting Drone Simulator (Viper-01 & Raven-02)..."
python3 src/python/vision/video_simulator.py &

# 3. Start the Frontend
echo "💻 Starting Dashboard Frontend on http://localhost:3000..."
cd src/frontend && python3 -m http.server 3000 &

# Wait for all background processes
wait
