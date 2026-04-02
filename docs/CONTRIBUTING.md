# Contributing to AMC-Grid C2

**Last Updated: 2026-03-19**

This guide covers development setup, testing, code style, and the PR process for AMC-Grid.

## Development Setup

### Prerequisites

- **Python 3.10+** (verify with `python3 --version`)
- **Git** for version control
- **Node.js 18+** for frontend tooling (optional, for E2E tests)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/EthanSheehan/AMC-Grid.git
cd AMC-Grid

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install Python dependencies
./venv/bin/pip install -r requirements.txt

# Install optional: Node.js dependencies for E2E tests
npm install
```

### Environment Configuration

```bash
# Copy example to create .env
cp .env.example .env

# Edit .env and add API keys (optional — system works without them)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=claude-...
# GEMINI_API_KEY=AIza...
```

## Available Commands

### AUTO-GENERATED: Script Reference

| Command | Purpose | Runs |
|---------|---------|------|
| `./amc-grid.sh` | Launch complete system (backend + frontend + simulator) | FastAPI (:8000) + HTTP Server (:3000) + Simulator |
| `./amc-grid.sh --demo` | Launch in demo auto-pilot mode (full F2T2EA kill chain) | All components + auto-approvals |
| `./amc-grid.sh --demo --no-sim` | Demo mode without drone video simulator | Backend + frontend only |
| `./venv/bin/python3 src/python/api_main.py` | Run FastAPI backend only | WebSocket server on :8000 |
| `cd src/frontend && python3 serve.py 3000` | Run dashboard frontend only (no-cache) | Dev HTTP server on :3000 |
| `./venv/bin/python3 src/python/vision/video_simulator.py` | Run drone simulator only | Connects to :8000/ws |
| `./venv/bin/python3 -m pytest src/python/tests/` | Run all Python tests | 214+ test cases |
| `./venv/bin/python3 -m pytest src/python/tests/test_FILENAME.py` | Run single test file | Single test module |
| `npm run test:e2e` | Run Playwright E2E tests | Browser-based tests |
| `npm run test:e2e:ui` | Run E2E tests with UI | Interactive test runner |
| `npm run test:e2e:debug` | Debug E2E tests with inspector | Step through tests |
| `npm run test:e2e:critical` | Run critical path tests only | 6 core user flows |
| `./venv/bin/pip install -r requirements.txt` | Install/update Python dependencies | Updates venv |

### Common Development Tasks

**Run the full system:**
```bash
./amc-grid.sh
# Opens browser at http://localhost:3000
# API docs available at http://localhost:8000/docs
```

**Run backend only (for testing):**
```bash
./venv/bin/python3 src/python/api_main.py
```

**Run tests with coverage:**
```bash
./venv/bin/python3 -m pytest src/python/tests/ -v --cov=src/python --cov-report=html
```

**Run specific test:**
```bash
./venv/bin/python3 -m pytest src/python/tests/test_sim_integration.py -v
```

**Run E2E tests (requires running backend):**
```bash
# In one terminal
./amc-grid.sh

# In another terminal
npm run test:e2e:headed
```

## Testing Requirements

### Test Coverage

- **Minimum: 80% code coverage** on all new code
- **Unit tests**: For individual functions and utilities
- **Integration tests**: For API endpoints and database operations
- **E2E tests**: For critical user flows

### Test-Driven Development (Mandatory)

Every feature or bug fix follows this workflow:

1. **RED** — Write failing test first
2. **GREEN** — Implement minimal code to pass test
3. **IMPROVE** — Refactor while tests still pass
4. **VERIFY** — Confirm 80%+ coverage

Example for a new agent method:

```python
# test_new_agent.py
import pytest
from agents.new_agent import NewAgent

def test_new_agent_processes_detection():
    """NewAgent should process detection and update state."""
    agent = NewAgent()
    detection = Detection(...)
    result = agent.process(detection)
    assert result.status == "processed"
    assert len(result.recommendations) > 0

# agents/new_agent.py
def process(self, detection):
    return AgentResult(status="processed", recommendations=[...])
```

### Running Tests

```bash
# All tests
./venv/bin/python3 -m pytest src/python/tests/

# Single test file
./venv/bin/python3 -m pytest src/python/tests/test_sim_integration.py

# Single test function
./venv/bin/python3 -m pytest src/python/tests/test_sim_integration.py::test_drone_repositioning

# With verbose output
./venv/bin/python3 -m pytest src/python/tests/ -v

# With coverage report
./venv/bin/python3 -m pytest src/python/tests/ --cov=src/python --cov-report=term-missing
```

### E2E Test Structure

Critical user flows are tested with Playwright:

```bash
# Run only critical tests (6 core flows)
npm run test:e2e:critical

# Run with browser visible (headed mode)
npm run test:e2e:headed

# Debug with Playwright Inspector
npm run test:e2e:debug

# View test report
npm run test:e2e:report
```

## Code Style

### Python Code Style

Follow **PEP 8** with these project conventions:

- **Line length**: 100 characters (pragmatic, not strict)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Type hints**: Used on public API methods, optional on internal code
- **Immutability**: Create new objects, never mutate existing ones (Pydantic models are good)
- **Error handling**: Explicit handling at all boundaries
- **Function size**: Keep under 50 lines; extract helpers for larger functions
- **File size**: Keep under 800 lines; split large modules

### Example: Good Code

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Detection:
    """Immutable detection record."""
    threat_id: str
    confidence: float
    location: tuple

    def update_confidence(self, new_confidence: float) -> "Detection":
        """Return new Detection with updated confidence (immutable)."""
        if new_confidence < 0 or new_confidence > 1.0:
            raise ValueError("Confidence must be between 0 and 1")
        return Detection(
            threat_id=self.threat_id,
            confidence=new_confidence,
            location=self.location,
        )

def process_detection(detection: Detection) -> str:
    """Process a detection and return status."""
    try:
        updated = detection.update_confidence(0.95)
        return f"Processed {updated.threat_id}"
    except ValueError as e:
        logger.error("Invalid detection", error=str(e))
        raise
```

### JavaScript Code Style

- **Style**: Vanilla JS (no build step required)
- **Format**: 2-space indentation, semicolons optional (ESLint used in tests)
- **Modules**: ES6 imports/exports in `src/frontend/`
- **Comments**: JSDoc for public functions

### Frontend Architecture

- **Entry point**: `src/frontend/app.js` — orchestrates module init, wires WebSocket state to all UI components
- **No build step**: Served by `serve.py` (custom no-cache HTTP server, replaces `python3 -m http.server`)
- **Modules**: Each feature has a dedicated `.js` file
  - `state.js` — Shared application state (selected drone/target, viewer, WebSocket, theater bounds)
  - `websocket.js` — WebSocket client and event dispatch
  - `map.js` — Cesium 3D viewer initialization, zone rendering, `flyToTheater()` for theater switching
  - `drones.js` — UAV 3D entity rendering, model management, lock indicators
  - `dronelist.js` — Drone card sidebar with inline mode command buttons (SEARCH/FOLLOW/PAINT/INTERCEPT)
  - `dronecam.js` — Drone Camera PIP: canvas-based synthetic feed with HUD, crosshair, lock box
  - `targets.js` — Target visualization and threat ring rendering
  - `enemies.js` — ENEMIES tab with threat assessment, tracker tags showing which UAVs track each target
  - `assistant.js` — Tactical AIP message feed widget
  - `strikeboard.js` — HITL nomination + COA approval UI
  - `sidebar.js` — Tab navigation (MISSION / ASSETS / ENEMIES) + global controls
  - `theater.js` — Theater selector dropdown, triggers auto-recenter on switch
  - `rangerings.js` — Sensor range ring overlays per drone
  - `mapclicks.js` — Map click handlers (waypoints, spikes)
  - `detailmap.js` — Detail waypoint placement modal

## Contributing Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feat/your-feature-name
# or: git checkout -b fix/bug-description
# or: git checkout -b docs/documentation-update
```

### 2. Develop with TDD

```bash
# Write test first (RED)
# Then implement (GREEN)
# Then refactor (IMPROVE)

./venv/bin/python3 -m pytest src/python/tests/ -v
```

### 3. Run Full Test Suite Before Commit

```bash
# Python tests
./venv/bin/python3 -m pytest src/python/tests/ --cov=src/python

# E2E tests (optional but recommended)
npm run test:e2e:critical
```

### 4. Commit with Conventional Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: <type>: <description>

git commit -m "feat: Add ROE evaluation to strategy analyst"
git commit -m "fix: Correct UAV fuel consumption calculation"
git commit -m "docs: Update API endpoint documentation"
git commit -m "test: Add edge case tests for sensor model"
git commit -m "refactor: Extract detection processing to utility"

# Types: feat, fix, docs, test, refactor, perf, chore, ci
```

### 5. Push and Open Pull Request

```bash
git push -u origin feat/your-feature-name
# Then open PR on GitHub

# PR title: Brief one-liner
# PR body: What changed, why, how to test
```

## Code Review Checklist

Every PR should address:

- [ ] **Tests**: New code has 80%+ test coverage
- [ ] **No hardcoded values**: Use config/env vars
- [ ] **Error handling**: All exceptions caught and logged
- [ ] **Type safety**: Type hints on public methods
- [ ] **Immutability**: No in-place mutations
- [ ] **Documentation**: README/docstrings updated
- [ ] **Performance**: No obvious inefficiencies
- [ ] **Security**: No secrets, injection vulnerabilities, etc.

## Architecture Guidelines

### Three Main Subsystems

**1. FastAPI Backend** (`src/python/api_main.py`)
- WebSocket server running 10Hz simulation loop
- Dual-client model: DASHBOARD (frontend) + SIMULATOR (drone)
- Broadcasts full state each tick
- Agents embedded in event loop

**2. Simulation Engine** (`src/python/sim_engine.py`)
- `SimulationModel` manages UAV and target states
- Probabilistic detection with Pd/RCS models (`sensor_model.py`)
- Zone-based coverage optimization with imbalance-driven repositioning
- 10 target unit types: SAM, TEL, TRUCK, CP, MANPADS, RADAR, C2_NODE, LOGISTICS, ARTILLERY, APC
- 5 target behaviors: stationary, patrol, shoot-and-scoot, ambush, concealment/flee
- 7 UAV flight modes: IDLE, SEARCH, FOLLOW, PAINT, INTERCEPT, REPOSITIONING, RTB
- Fixed-wing physics with `_turn_toward()` for smooth heading changes

**3. Cesium Frontend** (`src/frontend/`)
- Vanilla JS with Cesium for 3D visualization (no build step, served by `serve.py`)
- WebSocket connection to backend at `ws://localhost:8000/ws`
- Tab-based UI: MISSION / ASSETS / ENEMIES
- Real-time entity updates at 10Hz
- Drone Camera PIP with HUD overlays, tracking reticle, lock box
- Inline mode command buttons (SEARCH/FOLLOW/PAINT/INTERCEPT) in drone cards
- Auto-recenter camera when switching theaters
- ENEMIES tab shows tracker tags (which UAVs are tracking each target)

### AI Agent Pipeline

```
Detection → ISR Observer → Strategy Analyst
→ [HITL Gate 1] → Tactical Planner
→ [HITL Gate 2] → Effectors Agent → Assessment
```

Each agent:
- Operates in **heuristic mode** by default (no API keys needed)
- Upgrades to **LLM mode** when `.env` has API keys
- Uses **multi-provider fallback**: Gemini → Anthropic → Ollama → heuristic
- Communicates via Pydantic models in `src/python/core/ontology.py`

### Adding a New Agent

1. Create `src/python/agents/my_agent.py` with `MyAgent` class
2. Implement required methods: `invoke()` or `stream()`
3. Add tests in `src/python/tests/test_my_agent.py`
4. Wire into pipeline in `src/python/api_main.py`
5. Update this guide with agent description

### Adding a New Endpoint

1. Create function in `api_main.py` with `@app.post()` or `@app.get()` decorator
2. Use Pydantic models for request/response validation
3. Add error handling with meaningful messages
4. Write integration test in `src/python/tests/test_agent_wiring.py`
5. Document in README.md

## UAV Flight Modes

The simulation engine implements 7 UAV flight modes with fixed-wing physics. All modes use `_turn_toward()` for gradual heading changes (max 3 deg/sec standard rate turn).

| Mode | Trigger | Behavior | Orbit Radius | Target State |
|------|---------|----------|-------------|--------------|
| **IDLE** | Default / service timer expired | Stationary hold at assigned position | N/A | N/A |
| **SEARCH** | `scan_area` action or zone demand | Constant-rate circular loiter via `MAX_TURN_RATE` over assigned zone | ~3 km (`LOITER_RADIUS_DEG`) | N/A (releases target) |
| **FOLLOW** | `follow_target` action | Loose orbit maintaining visual contact; smooth fixed-wing arcs | ~2 km (`FOLLOW_ORBIT_RADIUS_DEG`) | TRACKED |
| **PAINT** | `paint_target` action | Tight orbit with laser designation for weapons guidance | ~1 km (`PAINT_ORBIT_RADIUS_DEG`) | LOCKED |
| **INTERCEPT** | `intercept_target` action | Direct approach at 1.5x speed, then danger-close orbit | ~300 m (`INTERCEPT_CLOSE_DEG`) | LOCKED |
| **REPOSITIONING** | Coverage imbalance or waypoint command | Direct flight to new position with 3x turn rate | N/A (transit) | N/A |
| **RTB** | Fuel below 1.0 hours | Return to base coordinates | N/A (transit) | N/A |

### Mode Transitions

- **SEARCH** releases any target assignment and resumes area patrol
- **FOLLOW/PAINT/INTERCEPT** require a target selection (via ENEMIES tab click or map click)
- **RTB** triggers automatically when `fuel_hours < 1.0`
- **cancel_track** returns the UAV to SEARCH and resets target state to DETECTED

### Orbit Physics

All tracking modes (FOLLOW, PAINT, INTERCEPT) use smooth fixed-wing arcs:

1. Calculate desired velocity vector toward/around the target
2. Mix radial (toward/away) and tangential (orbit) components based on distance
3. `_turn_toward()` gradually adjusts heading within `MAX_TURN_RATE` limit
4. Result: realistic fixed-wing circular orbits, not instantaneous position snaps

For FOLLOW/PAINT, the orbit balance works like:
- **Too close** (< 0.8x orbit radius): push outward (stronger radial, weaker tangential)
- **Too far** (> 1.2x orbit radius): pull inward (stronger radial, weaker tangential)
- **In band**: pure tangential (smooth circle)

For INTERCEPT, the UAV flies straight at the target at 1.5x speed until within `INTERCEPT_CLOSE_DEG` (~300m), then switches to a tight tangential orbit.

## Drone Camera PIP

The Drone Camera (`dronecam.js`) provides a canvas-based synthetic sensor feed that appears as a picture-in-picture overlay when a UAV is selected.

### Camera Projection

Targets are projected into the camera view using:
1. **Haversine distance** — filter targets beyond `SENSOR_RANGE_KM` (15 km)
2. **Bearing calculation** — compute relative bearing from drone heading
3. **FOV clipping** — discard targets outside `HFOV_DEG` (60 degrees)
4. **Screen mapping** — horizontal position from relative angle, vertical from distance factor

### HUD Elements

| Element | Location | Content |
|---------|----------|---------|
| Telemetry | Top-left | UAV ID, altitude (km), heading |
| Mode indicator | Below telemetry | Current mode with color coding |
| Position | Top-right | Lat/Lon coordinates |
| Tracking info | Top-right (when tracking) | Target type/ID, range, bearing |
| Lock status | Top-right (PAINT mode) | "LOCK: ACTIVE" in red |
| Target info panel | Bottom-left (when tracking) | Target state, range/bearing, confidence |
| Timestamp | Bottom-center | UTC time |

### Target Rendering

Each target type has a unique shape and color:

| Type | Shape | Color |
|------|-------|-------|
| SAM | Diamond | Red |
| TEL | Triangle | Orange |
| TRUCK | Rectangle | White |
| CP | Square | Orange |
| MANPADS | Circle | Purple |
| RADAR | Hexagon | Cyan |
| C2_NODE | Diamond | Yellow |
| LOGISTICS | Rectangle | Gray |
| ARTILLERY | Triangle | Red |
| APC | Square | Green |

### Tracking Overlays

- **Reticle**: Green crosshair with gap (appears when tracking any target)
- **Lock Box**: Pulsing red rectangle (PAINT mode only) — oscillates size and opacity
- **Corner brackets**: Green L-shaped brackets at target bounding box corners

## Target Behaviors

The simulation models 5 distinct target behaviors based on unit type:

| Behavior | Unit Types | Description |
|----------|-----------|-------------|
| **Stationary** | SAM, CP, RADAR, C2_NODE | Fixed position, no movement |
| **Patrol** | TRUCK, LOGISTICS | Follow 3-5 random waypoints in a loop; LOGISTICS moves at 0.5x speed |
| **Shoot-and-scoot** | TEL | Stationary until relocate timer expires (30-60s), then teleports to random position; hides when concealed |
| **Ambush** | MANPADS | Stationary until UAV within 5 km, then flees to random position with 15s cooldown |
| **Concealment** | TEL, MANPADS | Activates when UAV within 3 km; stops movement and reduces detectability |

### Radar Emitter Toggle

SAM and RADAR types periodically toggle `is_emitting` with `EMIT_TOGGLE_PROB` (0.5% per tick). SIGINT sensors can only detect emitting targets.

## Probabilistic Detection Model

Detection uses a physics-informed probability model (`sensor_model.py`):

### Sensor Types

| Sensor | Max Range | Weather Sensitivity | Requires Emitter | Resolution |
|--------|-----------|-------------------|-------------------|------------|
| **EO/IR** | 50 km | 0.8 (highly affected) | No | 1.0 (best) |
| **SAR** | 100 km | 0.2 (mostly immune) | No | 0.7 |
| **SIGINT** | 200 km | 0.0 (immune) | Yes | 0.3 (lowest) |

### Detection Formula

```
snr_norm = (1 - (range/max_range)^2) + rcs_gain * 0.3 - weather_penalty
Pd = sigmoid(snr_norm * 10 - 5)
```

Where:
- **rcs_gain** = log10(effective_RCS / reference_RCS) — larger targets are easier to detect
- **weather_penalty** = weather_sensitivity * (cloud_cover + precipitation * 0.5) * 0.6
- **effective_RCS** = base_RCS * aspect_factor — broadside (90 degrees) gives 1.5x, head-on gives 0.3x
- **confidence** = Pd * sensor_resolution_factor

### RCS Table (Radar Cross-Section)

| Unit Type | Base RCS (m^2) | Detectability |
|-----------|---------------|---------------|
| RADAR | 20.0 | Very easy |
| SAM | 15.0 | Easy |
| TEL | 10.0 | Medium |
| CP | 8.0 | Medium |
| C2_NODE | 6.0 | Medium |
| TRUCK | 5.0 | Medium |
| LOGISTICS | 4.0 | Harder |
| MANPADS | 0.5 | Very hard |

## Environment Variables

### AUTO-GENERATED: Environment Documentation

| Variable | Type | Required | Default | Purpose |
|----------|------|----------|---------|---------|
| `OPENAI_API_KEY` | string | No | (empty) | OpenAI API key for agent LLM reasoning |
| `ANTHROPIC_API_KEY` | string | No | (empty) | Anthropic Claude API key (fallback provider) |
| `GEMINI_API_KEY` | string | No | (empty) | Google Gemini API key (primary LLM) |
| `HOST` | string | No | `0.0.0.0` | Server bind address |
| `PORT` | integer | No | `8000` | FastAPI server port |
| `LOG_LEVEL` | string | No | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR |
| `SIMULATION_HZ` | integer | No | `10` | Simulation tick rate (Hz) |
| `WS_BACKEND_URL` | string | No | `ws://localhost:8000/ws` | WebSocket backend URL (used by simulator) |
| `DEFAULT_THEATER` | string | No | `romania` | Default theater: romania, south_china_sea, baltic |

**For local development**, copy `.env.example` to `.env` and leave API keys empty. The system runs fully with heuristic agents.

**For production**, ensure all required API keys are set via environment variables (never hardcode).

## Troubleshooting

### Backend won't start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
kill -9 <PID>

# Try again
./venv/bin/python3 src/python/api_main.py
```

### Tests fail with import errors

```bash
# Reinstall dependencies
./venv/bin/pip install -r requirements.txt --force-reinstall

# Clear pytest cache
rm -rf .pytest_cache __pycache__

# Try again
./venv/bin/python3 -m pytest src/python/tests/ -v
```

### WebSocket connection fails

```bash
# Verify backend is running
curl http://localhost:8000/api/theaters

# Check if .env has correct WS_BACKEND_URL
cat .env | grep WS_BACKEND_URL
```

### E2E tests timeout

```bash
# Run with longer timeout
npm run test:e2e:headed -- --timeout=60000

# Or run tests one at a time
npm run test:e2e -- --workers=1
```

## Additional Resources

- **Architecture**: See [CLAUDE.md](../CLAUDE.md)
- **API Docs**: `http://localhost:8000/docs` (when running)
- **Coding Standards**: [Coding Style Rules](https://github.com/EthanSheehan/AMC-Grid/blob/main/.claude/rules/coding-style.md)
- **Testing Guide**: [Testing Requirements](https://github.com/EthanSheehan/AMC-Grid/blob/main/.claude/rules/testing.md)
- **Git Workflow**: [Git Workflow](https://github.com/EthanSheehan/AMC-Grid/blob/main/.claude/rules/git-workflow.md)

## Questions?

Open an issue or discussion on GitHub with the `question` label.
