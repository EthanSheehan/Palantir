# AMC-Grid Codemaps Index

**Last Updated: 2026-03-19**

This document provides an architectural overview of AMC-Grid C2. For detailed component guides, see the codemaps directory (coming soon).

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cesium Dashboard (Frontend)               │
│                   src/frontend/ (Vanilla JS)                 │
│        (3D visualization, WebSocket client, UI tabs)         │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket (10Hz)
                         │ ws://localhost:8000/ws
┌────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend                            │
│         src/python/api_main.py (AsyncIO server)              │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │        Simulation Engine (10Hz loop)                │    │
│  │      src/python/sim_engine.py                       │    │
│  │  (UAVs, targets, zones, physics, weather)          │    │
│  └─────────────────────────────────────────────────────┘    │
│                         │                                     │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │     Kill Chain Agent Pipeline (F2T2EA)             │    │
│  │                                                     │    │
│  │  ISR Observer → Strategy Analyst → Tactical        │    │
│  │  Planner → Effectors Agent                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │        HITL Manager (Two-Gate Approval)             │    │
│  │  src/python/hitl_manager.py                         │    │
│  │  (Nomination gate, COA authorization gate)          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ Telemetry (video, position)
                         │
┌────────────────────────┴────────────────────────────────────┐
│              Drone Simulator (Optional)                      │
│        src/python/vision/video_simulator.py                 │
│     (UAV telemetry generator, video frames)                │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
src/
├── python/
│   ├── api_main.py                # FastAPI server + WebSocket + event loop
│   ├── sim_engine.py              # Physics simulation (UAVs, targets, zones)
│   ├── config.py                  # Pydantic-Settings environment management
│   ├── pipeline.py                # F2T2EA orchestration logic
│   ├── hitl_manager.py            # Human-in-the-loop approval system
│   ├── theater_loader.py          # YAML scenario loader
│   ├── llm_adapter.py             # Multi-provider LLM fallback chain
│   ├── sensor_model.py            # Probabilistic detection (Pd/RCS)
│   ├── logging_config.py          # Structlog configuration
│   │
│   ├── core/
│   │   ├── ontology.py            # Shared Pydantic models (Detection, Target, etc.)
│   │   └── state.py               # LangGraph state + annotated reducers
│   │
│   ├── agents/                    # F2T2EA Agent Pipeline
│   │   ├── isr_observer.py        # Find/Fix/Track (sensor fusion)
│   │   ├── strategy_analyst.py    # Target (ROE evaluation, priority scoring)
│   │   ├── tactical_planner.py    # Engage (COA generation)
│   │   ├── effectors_agent.py     # Assess (execution, battle damage assessment)
│   │   ├── pattern_analyzer.py    # Activity pattern analysis
│   │   ├── ai_tasking_manager.py  # Sensor retasking optimization
│   │   ├── battlespace_manager.py # Map layers + threat rings
│   │   └── synthesis_query_agent.py  # SITREP generation
│   │
│   ├── schemas/
│   │   └── ontology.json          # JSON serialization of ontology
│   │
│   ├── mission_data/
│   │   ├── historical_activity.py # Activity pattern database
│   │   └── asset_registry.py      # Friendly force registry
│   │
│   ├── vision/
│   │   ├── video_simulator.py     # Drone simulator entry point
│   │   └── ...                    # Vision pipeline modules
│   │
│   └── tests/                     # 214+ pytest test cases
│       ├── conftest.py            # Pytest fixtures
│       ├── test_agent_wiring.py
│       ├── test_sim_integration.py
│       ├── test_hitl_manager.py
│       ├── test_llm_adapter.py
│       └── ... (10+ more test modules)
│
├── frontend/                      # Cesium 3D Dashboard (Vanilla JS)
│   ├── index.html                 # Main HTML (imports Cesium CDN)
│   ├── app.js                     # Entry point (~1500 lines)
│   ├── state.js                   # Application state management
│   ├── websocket.js               # WebSocket client + event dispatch
│   ├── map.js                     # Cesium viewer initialization
│   ├── drones.js                  # UAV visualization + list UI with inline mode buttons
│   ├── dronecam.js                # Drone Camera PIP — canvas synthetic feed with HUD
│   ├── targets.js                 # Target/threat ring rendering
│   ├── enemies.js                 # ENEMIES tab with threat assessment
│   ├── strikeboard.js             # HITL approval UI
│   ├── sidebar.js                 # Tab navigation + controls
│   ├── assistant.js               # Tactical AIP message feed
│   ├── theater.js                 # Theater selector
│   ├── serve.py                   # No-cache dev HTTP server (replaces http.server)
│   └── style.css                  # Dark theme styles
│
theaters/
├── romania.yaml                   # Default theater configuration
├── south_china_sea.yaml           # Pacific scenario
└── baltic.yaml                    # Baltic scenario

docs/
├── CONTRIBUTING.md                # Development guide (scripts, testing, style)
├── RUNBOOK.md                     # Operations guide (deployment, scaling, issues)
├── CODEMAPS.md                    # This file — architectural overview
├── PRD.md                         # Product requirements
├── PRD_v2_upgrade.md              # v2 upgrade roadmap
├── project_charter.md             # Project vision
└── prompts/                       # Agent system prompts (10+ agents)
```

## Key Modules

### FastAPI Backend (`src/python/api_main.py`)

**Purpose**: Core server, WebSocket management, event loop orchestration

**Responsibilities**:
- Accept WebSocket connections from dashboard and simulator clients
- Run 10Hz simulation loop
- Broadcast full simulation state each tick
- Route WebSocket messages to appropriate handlers
- Manage client type registration (DASHBOARD vs SIMULATOR)

**Key Functions**:
- `@app.websocket("/ws")` — Main WebSocket handler
- `broadcast_state()` — Send state to all DASHBOARD clients
- `simulation_loop()` — 10Hz tick (simulation + agents + HITL)
- Health checks: `@app.get("/api/theaters")`

**Dependencies**: FastAPI, WebSockets, structlog, Pydantic

**Related Files**:
- `config.py` — Environment variable management
- `sim_engine.py` — Simulation state updates
- `pipeline.py` — Agent orchestration
- `hitl_manager.py` — Strike board logic

### Simulation Engine (`src/python/sim_engine.py`)

**Purpose**: Physics-based tactical simulation

**Responsibilities**:
- Track UAV positions, modes, fuel, endurance
- Move targets with type-specific AI behaviors
- Calculate zone-based coverage and imbalance
- Generate probabilistic detections
- Update environment (weather, time of day)

**Key Classes**:
- `SimulationModel` — Central state container
  - `.step()` — One simulation tick
  - `.detect_targets()` — Probabilistic detection with Pd/RCS
  - `.move_targets()` — Target movement AI
  - `.reposition_uavs()` — Zone-based optimization
- `UAV`, `Target`, `Zone` — Entity models

**Unit Types**: SAM, TEL, TRUCK, CP, MANPADS, RADAR, C2_NODE, LOGISTICS, ARTILLERY, APC

**UAV Modes**: IDLE, SEARCH, FOLLOW, PAINT, INTERCEPT, REPOSITIONING, RTB
- SEARCH: circular loiter via MAX_TURN_RATE
- FOLLOW: ~2km orbit, smooth fixed-wing arcs via `_turn_toward()`
- PAINT: ~1km tight orbit, laser designation, target → LOCKED
- INTERCEPT: direct approach at 1.5x speed, ~300m danger-close orbit, target → LOCKED
- REPOSITIONING: zone rebalance flight at 3x turn rate
- RTB: low fuel return to base

**Target Behaviors**: patrol, ambush, shoot-and-scoot, concealment, flee

**Related Files**:
- `sensor_model.py` — Detection probability calculations
- `theater_loader.py` — Scenario initialization

### AI Agent Pipeline

**Architecture**: LangGraph + LangChain with Pydantic state

**Pipeline**:
```
Detection
    ↓
[ISR Observer] → Find/Fix/Track (sensor fusion)
    ↓
[Strategy Analyst] → Target (ROE eval, priority)
    ↓
[HITL Gate 1] ← Nomination approval
    ↓
[Tactical Planner] → Engage (COA generation)
    ↓
[HITL Gate 2] ← COA authorization
    ↓
[Effectors Agent] → Assess (execution, BDA)
    ↓
State/SITREP
```

**Key Features**:
- **Heuristic Mode**: Built-in decision logic (no LLM needed)
- **LLM Mode**: Multi-provider fallback (Gemini → Anthropic → Ollama)
- **HITL Gates**: Two approval points for strike authorization
- **Async Processing**: All agents support streaming + async invoke

**Modules**:
- `isr_observer.py` — Detections + track management
- `strategy_analyst.py` — ROE rules + target prioritization
- `tactical_planner.py` — COA generation (heuristic or LLM)
- `effectors_agent.py` — Strike execution + BDA
- `pattern_analyzer.py` — Historical activity pattern matching
- `ai_tasking_manager.py` — Sensor retasking optimization
- `battlespace_manager.py` — Map visualization layers
- `synthesis_query_agent.py` — SITREP query generation

**State Management** (`src/python/core/state.py`):
- Uses LangGraph annotated state with `add` reducers
- Accumulates detections, nominations, COAs, rejections
- Enables multi-round reasoning with full history

**Shared Data Contracts** (`src/python/core/ontology.py`):
- `Detection` — Raw sensor input
- `TargetClassification` — Inferred identity + type
- `TargetNomination` — Strike board entry
- `CourseOfAction` — Engagement plan
- `EngagementDecision` — Strike authorization
- `BattleDamageAssessment` — Post-strike assessment

### Cesium Frontend (`src/frontend/`)

**Purpose**: Real-time 3D tactical visualization + HITL UI

**Architecture**: Vanilla JavaScript (no build step), Cesium.js for 3D

**Modules**:
- `app.js` — Entry point, module initialization
- `state.js` — Shared application state (drones, targets, UI state)
- `websocket.js` — WebSocket client, event dispatcher
- `map.js` — Cesium viewer setup, entity factory
- `drones.js` — UAV rendering + drone list sidebar with inline mode command buttons (SEARCH/FOLLOW/PAINT/INTERCEPT)
- `dronecam.js` — Drone Camera PIP (picture-in-picture): canvas-based synthetic feed with HUD, tracking reticle, lock box
- `targets.js` — Target visualization, threat ring rendering
- `enemies.js` — ENEMIES tab with threat assessment rows
- `strikeboard.js` — HITL nomination + COA approval UI
- `sidebar.js` — Tab navigation (MISSION / ASSETS / ENEMIES)
- `assistant.js` — Tactical AIP message feed widget
- `theater.js` — Theater selector dropdown (triggers auto-recenter on switch)

**UI Tabs**:
1. **MISSION** — Map view with drones/targets/threat rings
2. **ASSETS** — Drone list, status, fuel, operational mode
3. **ENEMIES** — Target list with threat assessment, priority

**Capabilities**:
- Real-time entity updates (10Hz WebSocket)
- Cesium primitives (points, polylines, polygons, models)
- Camera controls (follow target, orbit, reset)
- Strike board interaction (approve/reject nominations and COAs)
- SITREP query interface

**Dependencies**: Cesium JS (CDN), no npm build required

### HITL Manager (`src/python/hitl_manager.py`)

**Purpose**: Two-gate human approval system for strikes

**Gates**:
1. **Nomination Gate** — Operator approves target for consideration
2. **COA Gate** — Operator authorizes specific course of action

**State Machine**:
```
Detection → Nomination Pending → Approved → COA Pending → Authorized → Execute
                    ↓
                  Rejected
```

**UI Integration**:
- Strike board shows all pending nominations
- Each nomination displays target info + recommended COAs
- Operator can approve, reject, or request more info
- Audit trail of all decisions

## Data Flow Examples

### Example 1: Detection to Strike

```
1. UAV detects target (sensor_model.py)
   → Detection(threat_id, confidence, location)

2. ISR Observer processes detection (isr_observer.py)
   → Track created/updated
   → Detection added to state

3. Strategy Analyst evaluates (strategy_analyst.py)
   → Apply ROE filters (rules.yaml)
   → Calculate target priority (value, threat, position)
   → Return TargetNomination if meets criteria

4. [HITL Gate 1] — Operator reviews nomination (strikeboard.js)
   → Approve or reject

5. Tactical Planner generates COA (tactical_planner.py)
   → Heuristic: Select nearest capable UAV
   → LLM: Generate multiple COA options with reasoning

6. [HITL Gate 2] — Operator authorizes COA (strikeboard.js)
   → Approve or request alternative

7. Effectors Agent executes strike (effectors_agent.py)
   → Launch UAV or kinetic effect
   → Monitor impact
   → Generate BDA (battle damage assessment)

8. Assessment stored in state (state.py)
   → Used for future pattern matching
   → Feeds into next detection cycle
```

### Example 2: Theater Switching

```
1. Operator selects theater (theater.js dropdown)
   → POST /api/theater {"theater": "south_china_sea"}

2. Backend loads theater YAML (theater_loader.py)
   → Parse theaters/south_china_sea.yaml
   → Extract UAV positions, target positions, zone definitions
   → Reset SimulationModel with new scenario

3. Frontend receives updated state (websocket.js)
   → Cesium viewer resets to new theater bounds
   → All drones/targets repositioned
   → Mission timer reset
```

## External Dependencies

| Package | Version | Purpose | Usage |
|---------|---------|---------|-------|
| langgraph | ≥0.0.21 | Agent state machine | F2T2EA pipeline |
| langchain-openai | ≥0.0.8 | OpenAI integration | LLM fallback chain |
| langchain-core | ≥0.1.33 | LangChain base | Agent framework |
| pydantic | ≥2.0 | Data validation | Ontology models |
| fastapi | ≥0.109.0 | Web framework | API + WebSocket |
| uvicorn | ≥0.27.0 | ASGI server | async runner |
| numpy | ≥1.24.0 | Numerics | Physics sim |
| opencv-python | ≥4.8.0 | Computer vision | Video processing |
| structlog | ≥24.1.0 | Structured logging | JSON logs |
| websockets | ≥12.0 | WebSocket support | Client/server |
| requests | ≥2.31.0 | HTTP client | API calls |
| ollama | ≥0.4.0 | Ollama integration | LLM fallback |
| anthropic | ≥0.40.0 | Anthropic API | Claude integration |
| google-genai | ≥1.0.0 | Google Gemini API | LLM provider |
| pytest-asyncio | ≥0.23.0 | Async test runner | pytest async support |
| pyyaml | ≥6.0 | YAML parsing | Theater configs |

## Frontend Dependencies

| Package | Source | Purpose |
|---------|--------|---------|
| Cesium | CDN (1.104) | 3D geospatial visualization |
| No npm build | — | Direct HTML/JS serving (serve.py — no-cache dev server) |

## Testing Overview

- **214+ test cases** across 12 test modules
- **Unit tests**: Individual agent/function behavior
- **Integration tests**: API endpoints, sim engine, HITL
- **E2E tests**: Critical user flows (Playwright)
- **Coverage target**: 80%+ on all new code

### Test Modules

| Module | Tests | Scope |
|--------|-------|-------|
| `test_agent_wiring.py` | ~20 | Full pipeline integration |
| `test_sim_integration.py` | ~10 | Simulation engine + UAV logic |
| `test_hitl_manager.py` | ~15 | Strike board approval flow |
| `test_llm_adapter.py` | ~20 | Multi-provider LLM fallback |
| `test_sensor_model.py` | ~25 | Probabilistic detection |
| `test_effectors_agent.py` | ~25 | Execution + BDA |
| `test_ai_tasking_manager.py` | ~15 | Sensor retasking |
| `test_battlespace_manager.py` | ~15 | Map layers + visualization |
| `test_pattern_analyzer.py` | ~12 | Activity pattern matching |
| `test_synthesis_query_agent.py` | ~15 | SITREP generation |
| `test_theater_loader.py` | ~20 | YAML scenario loading |
| `test_vision_pipeline.py` | ~2 | Video processing |

### E2E Critical Tests

| Test | Flow | Status |
|------|------|--------|
| WebSocket Connection | Client connects + receives state | Must pass |
| Tab Navigation | Switch MISSION/ASSETS/ENEMIES | Must pass |
| Drone List | UAVs appear, update in real-time | Must pass |
| Enemy List | Targets appear with threat assessment | Must pass |
| Mission Status | Simulation state visible | Must pass |
| Tactical Assistant | AIP messages appear | Must pass |

## Configuration & Scenarios

### Environment Variables (`.env`)

See [CONTRIBUTING.md](CONTRIBUTING.md#environment-variables) for complete list.

**Key settings**:
- `OPENAI_API_KEY` — OpenAI API key (optional)
- `GEMINI_API_KEY` — Google Gemini key (optional, primary LLM)
- `PORT` — FastAPI server port (default: 8000)
- `SIMULATION_HZ` — Tick rate (default: 10)
- `DEFAULT_THEATER` — Initial scenario (default: romania)

### Theater Configuration (`theaters/*.yaml`)

Each theater defines:
- **Map bounds** (WGS-84 coordinates)
- **Friendly forces** (UAV positions, types, capabilities)
- **Threat forces** (target positions, types, patrol patterns)
- **Zones** (grid-based for coverage optimization)
- **Rules of Engagement** (constraints on strikes)

Example:
```yaml
metadata:
  name: "Romania"
  bounds: {north: 48.5, south: 43.5, east: 29.5, west: 20.5}

friendly:
  - id: "UAV-1"
    position: [46.0, 24.5]
    type: "MQ-9"
    fuel: 28.0

threats:
  - id: "SAM-1"
    position: [45.2, 24.8]
    type: "SAM"
    behavior: "patrol"

zones:
  - id: "north_sector"
    bounds: {n: 48.0, s: 46.5, e: 28.0, w: 24.0}
```

## UAV Flight Mode State Machine

```
                    ┌─────────────┐
         zone       │             │   fuel < 1h
         demand  ┌──│    IDLE     │──────────────┐
                 │  │             │               │
                 │  └──────┬──────┘               │
                 │         │ coverage              │
                 │         │ imbalance             │
                 │         ▼                       ▼
                 │  ┌──────────────┐       ┌──────────┐
                 │  │REPOSITIONING │       │   RTB    │
                 │  │  (3x turn)   │       │(to base) │
                 │  └──────┬───────┘       └──────────┘
                 │         │ arrived
                 │         ▼
                 │  ┌──────────────┐
                 └─▶│   SEARCH     │◀─── cancel_track
                    │(circle loiter)│
                    └──────┬───────┘
                           │ user command + target selected
                ┌──────────┼──────────┐
                ▼          ▼          ▼
         ┌──────────┐ ┌────────┐ ┌───────────┐
         │  FOLLOW  │ │ PAINT  │ │ INTERCEPT │
         │ (~2km    │ │(~1km   │ │(1.5x speed│
         │  orbit)  │ │ orbit) │ │ ~300m)    │
         │TGT:TRACK │ │TGT:LOCK│ │TGT:LOCK  │
         └──────────┘ └────────┘ └───────────┘
```

### Mode Physics Parameters

| Constant | Value | Physical Meaning |
|----------|-------|-----------------|
| `MAX_TURN_RATE` | 3 deg/sec | Standard rate turn for fixed-wing aircraft |
| `FOLLOW_ORBIT_RADIUS_DEG` | 0.018 (~2 km) | Loose surveillance orbit |
| `PAINT_ORBIT_RADIUS_DEG` | 0.009 (~1 km) | Tight laser designation orbit |
| `INTERCEPT_CLOSE_DEG` | 0.003 (~300 m) | Danger-close engagement distance |
| `LOITER_RADIUS_DEG` | 0.027 (~3 km) | SEARCH/IDLE circle radius |
| `SPEED_DEG_PER_SEC` | 0.005 | Base UAV cruise speed |

### Orbit Mechanics

All orbit modes use a radial/tangential velocity mixing algorithm:

```python
# Compute unit vectors
nx, ny = dx/dist, dy/dist      # radial (toward target)
tx, ty = -ny, nx                # tangential (perpendicular, CCW)

# Mix based on distance from ideal orbit
if dist < orbit_r * 0.8:       # too close → push out
    dvx = (-nx * weight + tx * (1-weight)) * speed
elif dist > orbit_r * 1.2:     # too far → pull in
    dvx = (nx * weight + tx * (1-weight)) * speed
else:                           # in band → pure tangent
    dvx = tx * speed

# Smooth heading change
uav._turn_toward(dvx, dvy, speed, dt_sec)
```

FOLLOW uses 0.3/0.7 radial/tangential weight. PAINT uses 0.4/0.6 (tighter correction).

## Target Behavior AI

```
                      ┌──────────────┐
                      │  STATIONARY  │ SAM, CP, RADAR, C2_NODE
                      │   vx=vy=0    │
                      └──────────────┘

┌────────────────────────────────────────────────────────────┐
│                      PATROL                                 │
│  TRUCK, LOGISTICS (0.5x speed)                             │
│                                                             │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐          │
│  │   WP 1    │───▶│   WP 2    │───▶│   WP 3    │──loop──▶│
│  └───────────┘    └───────────┘    └───────────┘          │
│  3-5 random waypoints generated at spawn                    │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                  SHOOT AND SCOOT (TEL)                      │
│                                                             │
│  [stationary 30-60s] ──timer──▶ [teleport to random pos]  │
│         ▲                              │                    │
│         └──────────────────────────────┘                    │
│  Conceals (stops moving) when UAV within 3km               │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                    AMBUSH (MANPADS)                         │
│                                                             │
│  [stationary] ──UAV within 5km──▶ [flee: random offset]   │
│       ▲                                    │                │
│       └────── 15s cooldown ────────────────┘                │
│  Conceals when UAV within 3km                              │
└────────────────────────────────────────────────────────────┘
```

## Probabilistic Sensor Model

The detection pipeline evaluates each UAV-target pair every tick:

```
For each target:
  For each UAV (skip RTB, REPOSITIONING):
    1. Compute aspect angle (bearing from UAV to target vs target heading)
    2. Look up base RCS from RCS_TABLE (e.g., SAM=15m², MANPADS=0.5m²)
    3. Modulate RCS by aspect: broadside=1.5x, head-on=0.3x
    4. Compute Pd via sigmoid(SNR_normalized)
    5. Roll random() < Pd → detected/not
    6. Keep best detection across all UAVs

  If detected:
    state: UNDETECTED → DETECTED
    confidence = Pd × sensor_resolution_factor
  If not detected and not actively tracked:
    confidence decays by 0.95x per tick
    Below 0.1 → reverts to UNDETECTED
```

### SNR Formula

```
snr_norm = range_term + rcs_gain - weather_penalty

range_term   = 1 - (range / max_range)²
rcs_gain     = log₁₀(effective_RCS / reference_RCS) × 0.3
weather_pen  = sensitivity × (cloud + precip × 0.5) × 0.6

Pd = sigmoid(snr_norm × 10 - 5)
```

## Drone Camera PIP Architecture

`dronecam.js` renders a 400×300 canvas that simulates a forward-looking sensor:

```
┌──────────────────────────────────────────────────────┐
│ UAV-3      ALT: 3.0km          45.23456N 24.56789E  │
│ HDG: 127.4                     TRK: SAM #7          │
│ MODE: PAINT                    RNG: 4521m BRG: 45.2 │
│                                LOCK: ACTIVE          │
│  ┌──────────────────────────────────────────────┐    │
│  │              ◇ SAM #7 [0.92]                 │    │
│  │           ┌─ ─ ─ ─ ─ ─┐                     │    │
│  │           │  ◇ [LOCK]  │  ← pulsing red box  │    │
│  │           └─ ─ ─ ─ ─ ─┘                     │    │
│  │     ─── + ───  ← tracking reticle            │    │
│  │                                               │    │
│  └──────────────────────────────────────────────┘    │
│ ┌─────────────────┐                                  │
│ │TGT: SAM #7      │  ← target info panel             │
│ │STATE: LOCKED     │                                  │
│ │RNG: 4521m        │                                  │
│ │CONF: 0.92        │                      12:34:56Z  │
│ └─────────────────┘                                  │
└──────────────────────────────────────────────────────┘
```

### Projection Pipeline

1. Filter targets beyond `SENSOR_RANGE_KM` (15 km) using haversine distance
2. Compute bearing from drone to target
3. Subtract drone heading to get relative angle
4. Clip to `HFOV_DEG` (±30 degrees from center)
5. Map horizontal: `nx = (relAngle / HFOV) + 0.5`
6. Map vertical: `ny = 0.3 + (1 - dist/maxDist) × 0.4` (closer = lower on screen)

## Theater Switching Data Flow

```
1. User selects theater in dropdown (theater.js)
   └── POST /api/theater {"theater": "south_china_sea"}

2. Backend reloads SimulationModel (api_main.py)
   ├── load_theater() parses theaters/south_china_sea.yaml
   ├── Reset all UAVs, targets, zones from YAML config
   └── get_state() now includes theater.bounds in payload

3. Frontend receives state with new theater name (app.js)
   ├── Detects theater name change: simState.theater.name !== currentTheater
   ├── Stores bounds in state.theaterBounds
   └── Calls flyToTheater(bounds)

4. Camera recenters (map.js)
   ├── Calculate center lat/lon from bounds
   ├── Calculate altitude from bounds span
   └── viewer.camera.flyTo() with smooth animation
```

## WebSocket Message Flow

```
┌──────────┐                          ┌──────────┐
│ Frontend │                          │ Backend  │
│(app.js)  │                          │(api_main)│
└────┬─────┘                          └────┬─────┘
     │  connect ws://localhost:8000/ws      │
     │─────────────────────────────────────▶│
     │                                      │
     │  {client_type: "DASHBOARD"}          │
     │─────────────────────────────────────▶│
     │                                      │
     │         {type: "state", payload:...} │ ← every 100ms (10Hz)
     │◀─────────────────────────────────────│
     │                                      │
     │  {action: "follow_target",           │
     │   drone_id: 3, target_id: 7}        │ ← user clicks FOLLOW button
     │─────────────────────────────────────▶│
     │                                      │ sim.command_follow(3, 7)
     │                                      │
     │  {type: "ASSISTANT_MESSAGE",         │
     │   payload: {agent: "isr_observer",   │ ← agent notification
     │   message: "New target detected"}}   │
     │◀─────────────────────────────────────│
     │                                      │
     │  {action: "approve_nomination",      │
     │   nomination_id: "nom-1"}            │ ← operator approves strike
     │─────────────────────────────────────▶│
     │                                      │
     │  {type: "HITL_UPDATE",               │
     │   payload: {event:                   │
     │   "nomination_approved"}}            │ ← strike board update
     │◀─────────────────────────────────────│
```

## Demo Auto-Pilot Mode

When `DEMO_MODE=true` or `--demo` flag is passed, `demo_autopilot()` runs as an async background task:

```
Loop every 2 seconds:
  1. Scan for targets in DETECTED/TRACKED state
  2. For eligible targets (not already nominated):
     ├── Create TargetNomination
     └── Add to HITL pending queue
  3. After 5s delay: auto-approve pending nominations
  4. Generate 3 COAs via tactical_planner heuristics
  5. After 3s delay: auto-authorize best COA
  6. Simulate engagement:
     ├── Roll probabilistic hit/kill
     ├── Update target state (DESTROYED / DAMAGED / ESCAPED)
     └── Broadcast HITL_UPDATE events
  7. All actions appear in Tactical AIP Assistant feed
```

A red "DEMO MODE" banner appears on the dashboard. No API keys required.

## Related Documentation

- **Contributing Guide**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Operations Runbook**: [RUNBOOK.md](RUNBOOK.md)
- **Simulation Deep-Dive**: [SIMULATION.md](SIMULATION.md)
- **Frontend Guide**: [FRONTEND.md](FRONTEND.md)
- **Product Requirements**: [PRD.md](PRD.md)
- **Development Guide**: [CLAUDE.md](../CLAUDE.md)
