# Ralph Agent Configuration

## Build Instructions

```bash
# Install Python dependencies
./venv/bin/pip install -r requirements.txt
```

## Test Instructions

```bash
# Run all tests
./venv/bin/python3 -m pytest src/python/tests/
```

## Run Instructions

```bash
# Launch everything (backend + frontend + drone simulator)
./amc-grid.sh

# Or run components individually:
./venv/bin/python3 src/python/api_main.py          # FastAPI backend on :8000
cd src/frontend && python3 -m http.server 3000      # Web UI on :3000
./venv/bin/python3 src/python/vision/video_simulator.py  # Drone simulator
```

## Notes
- Python project using FastAPI with Cesium frontend
- Use venv at `./venv/` for all Python commands
- Environment variables in `.env` file (loaded via python-dotenv)
- Required for AI agents: `OPENAI_API_KEY`
