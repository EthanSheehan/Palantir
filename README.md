# Palantir C2 — Multi-Agent Decision-Centric C2 System

![Project Status](https://img.shields.io/badge/status-active-success.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Overview

**Palantir C2** is a high-fidelity Command and Control system that automates the **F2T2EA kill chain** (Find, Fix, Track, Target, Engage, Assess) using multi-agent AI orchestration, a physics-based tactical simulator, and a Cesium 3D geospatial frontend.

The system features:

- **8 AI Agents** orchestrating the full kill chain pipeline with heuristic + LLM fallback
- **Human-in-the-Loop (HITL)** two-gate approval system for strike authorization
- **Physics-based simulation** with red force AI, 8 unit behaviors, and UAV fuel/endurance modeling
- **3 Theater configurations** (Romania, South China Sea, Baltic) with YAML-based scenario definition
- **Real-time Cesium 3D visualization** with WebSocket-driven 10Hz updates

## Quick Start

### Prerequisites

- **Python 3.10+** with venv
- **Web Browser** (Chrome/Safari/Firefox)

### Setup

```bash
# Clone and enter project
git clone <repo-url> && cd Palantir

# Create virtual environment and install dependencies
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Copy environment config (optional — system works without API keys)
cp .env.example .env
```

### Launch

```bash
./palantir.sh
```

This starts:
1. **FastAPI Backend** on `http://localhost:8000` (API + WebSocket server)
2. **Cesium Dashboard** on `http://localhost:3000` (3D tactical display)
3. **Drone Simulator** (UAV telemetry + video feeds)
4. Opens your browser automatically

#### Launcher Flags

| Flag | Description |
|------|-------------|
| `--demo` | Enable demo auto-pilot mode (full F2T2EA kill chain runs automatically) |
| `--no-sim` | Skip drone video simulator (useful if OpenCV not installed) |
| `--no-browser` | Don't auto-open the browser |

### Demo Mode

Run the full F2T2EA kill chain on auto-pilot with no human input:

```bash
./palantir.sh --demo
```

Demo mode automatically:
1. Detects targets via ISR Observer + Strategy Analyst
2. Nominates targets to the strike board
3. Auto-approves nominations after 5s delay
4. Generates 3 COAs via Tactical Planner heuristics
5. Auto-authorizes the best COA after 3s delay
6. Simulates engagement with probabilistic hit/kill outcomes
7. Updates target state (DESTROYED / DAMAGED / ESCAPED)

All actions are broadcast as real-time messages visible in the Tactical AIP Assistant feed. A red "DEMO MODE" banner appears on the dashboard. No API keys are required — the system runs entirely on heuristic agents.

For a lightweight demo without the drone video simulator:

```bash
./palantir.sh --demo --no-sim
```

### Run Components Individually

```bash
./venv/bin/python3 src/python/api_main.py                    # Backend only
cd src/frontend && python3 -m http.server 3000                # Dashboard only
./venv/bin/python3 src/python/vision/video_simulator.py       # Simulator only
DEMO_MODE=true ./venv/bin/python3 src/python/api_main.py     # Backend in demo mode
```

### Run Tests

```bash
./venv/bin/python3 -m pytest src/python/tests/                # All tests
./venv/bin/python3 -m pytest src/python/tests/test_sim_integration.py  # Single file
```

## Architecture

```
src/
  python/
    api_main.py              # FastAPI server + WebSocket + agent pipeline
    sim_engine.py            # Physics simulation (UAVs, targets, zones)
    pipeline.py              # F2T2EA kill chain orchestrator
    config.py                # Pydantic-settings env var management
    hitl_manager.py          # Two-gate HITL approval system
    theater_loader.py        # YAML theater configuration loader
    llm_adapter.py           # Multi-provider LLM fallback chain
    sensor_model.py          # Probabilistic detection (Pd/RCS)
    agents/
      isr_observer.py        # Find/Fix/Track — sensor fusion
      strategy_analyst.py    # Target — ROE evaluation + priority scoring
      tactical_planner.py    # Engage — COA generation
      effectors_agent.py     # Assess — execution + BDA
      pattern_analyzer.py    # Activity pattern analysis
      ai_tasking_manager.py  # Sensor retasking optimization
      battlespace_manager.py # Map layers + threat rings
      synthesis_query_agent.py # SITREP generation
    tests/                   # 214+ pytest tests
  frontend/
    app.js                   # Entry point (imports ES modules)
    index.html               # Cesium 3D viewer + sidebar UI
    style.css                # Dark theme styles
    state.js                 # Shared application state
    websocket.js             # WebSocket connection + event dispatch
    map.js                   # Cesium viewer initialization
    drones.js                # UAV entity rendering + drone list
    targets.js               # Target visualization + threat rings
    enemies.js               # ENEMIES tab with threat rows
    strikeboard.js           # Strike Board HITL UI
    sidebar.js               # Tab navigation + controls
    assistant.js             # Tactical AIP message feed
    theater.js               # Theater selector dropdown
theaters/
  romania.yaml               # Default theater config
  south_china_sea.yaml       # Pacific theater config
  baltic.yaml                # Baltic theater config
```

### AI Agent Pipeline

```
ISR Observer → Strategy Analyst → [HITL Gate 1: Nomination] → Tactical Planner → [HITL Gate 2: COA Auth] → Effectors Agent
```

Each agent works in **heuristic mode** by default (no API keys needed). When LLM keys are configured in `.env`, agents upgrade to LLM-backed reasoning via the multi-provider fallback chain (Gemini → Anthropic → Ollama → heuristic).

### Simulation

The sim engine models:
- **UAVs**: 7 operational modes (idle, scanning, tracking, painting, repositioning, RTB, serving), fuel consumption, zone-based coverage optimization
- **Targets**: 8 unit types (SAM, TEL, TRUCK, CP, MANPADS, RADAR, ARTILLERY, APC) with type-specific behaviors (patrol, ambush, shoot-and-scoot, concealment, flee)
- **Environment**: Time of day, cloud cover, precipitation affecting sensor performance
- **Detection**: Probabilistic Pd model incorporating range, RCS, weather penalties

### WebSocket Protocol

The backend broadcasts full simulation state as JSON at 10Hz to all connected dashboard clients. The protocol supports:
- `state` — full sim state (drones, targets, zones, strike board)
- `ASSISTANT_MESSAGE` — AI agent notifications (INFO/WARNING/CRITICAL)
- `HITL_UPDATE` — strike board nomination and COA status changes
- `SITREP_RESPONSE` — situation report query results
- Client actions: `spike`, `move_drone`, `view_target`, `follow_target`, `paint_target`, `cancel_track`, `approve_nomination`, `reject_nomination`, `authorize_coa`, `sitrep_query`, `retask_sensors`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/ws` | WebSocket (10Hz sim state + bidirectional commands) |
| POST | `/api/sitrep` | Generate situation report |
| POST | `/api/environment` | Set weather/time conditions |
| GET | `/api/theaters` | List available theaters |
| POST | `/api/theater` | Switch active theater |

## Environment Variables

See `.env.example` for all options. The system runs fully without API keys using heuristic agent mode.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (empty) | OpenAI API key (optional) |
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API key (optional) |
| `GEMINI_API_KEY` | (empty) | Google Gemini API key (optional) |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `SIMULATION_HZ` | `10` | Simulation tick rate |
| `DEFAULT_THEATER` | `romania` | Default theater to load |
| `DEMO_MODE` | `false` | Enable demo auto-pilot (or use `--demo` flag) |

## Contributing

1. Create a feature branch: `git checkout -b feat/new-feature`
2. Write tests first (TDD): `./venv/bin/python3 -m pytest src/python/tests/`
3. Commit changes: `git commit -m "feat: description"`
4. Push and open a PR

## License

MIT License — see [LICENSE](LICENSE) for details.
