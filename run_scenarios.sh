#!/bin/bash

# Scenario Runner for Project Antigravity

echo "🛠️ Available Scenarios:"
echo "1) Discovery (Default) - Multi-drone circular scan"
echo "2) Target Tracking (Mock) - Drones locked on specific sectors"
echo "3) Grid Search (Future) - Lawnmower pattern implementation"

read -p "Select a scenario [1-2]: " choice

case $choice in
    1)
        echo "🚀 Running Discovery Scenarios..."
        ./venv/bin/python3 src/python/vision/video_simulator.py
        ;;
    2)
        echo "🦁 Running Tracking Scenarios..."
        # In a real impl, we'd pass arguments here. For now, let's just run the simulator.
        ./venv/bin/python3 src/python/vision/video_simulator.py
        ;;
    *)
        echo "❌ Invalid choice."
        ;;
esac
