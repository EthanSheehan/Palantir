# Palantir C2 — Multi-Agent Decision-Centric Command & Control

![Project Status](https://img.shields.io/badge/status-active-success.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Overview

**Palantir C2** is a high-fidelity Command and Control system that automates the **F2T2EA kill chain** (Find, Fix, Track, Target, Engage, Assess) using multi-agent AI orchestration, coordinated drone swarm operations, a physics-based tactical simulator, and a Cesium 3D geospatial frontend.

- **9 AI Agents** orchestrating the full kill chain with heuristic + LLM fallback
- **Human-in-the-Loop (HITL)** two-gate approval system for strike authorization
- **Target Verification Pipeline** — 4-state machine (DETECTED → CLASSIFIED → VERIFIED → NOMINATED) with per-type thresholds, multi-sensor fusion, and operator manual override
- **Multi-Sensor Fusion** — complementary fusion across EO/IR, SAR, and SIGINT with max-within-type dedup
- **Swarm Coordination** — greedy UAV-to-target assignment with sensor-gap detection, priority scoring, and auto-release
- **Battlespace Assessment** — threat clustering, coverage gap identification, zone threat scoring, movement corridor detection
- **ISR Priority Queue** — automated sensor retasking based on threat weight, verification gaps, and sensor coverage
- **6 Map Modes** — OPERATIONAL, COVERAGE, THREAT, FUSION, SWARM, TERRAIN with keyboard shortcuts (1-6)
- **Enemy UAV Tracking** — adversary drone detection with RECON/ATTACK/JAMMING/EVADING modes
- **Intel Feed System** — subscription-filtered event streams (INTEL, COMMAND, SENSOR feeds)
- **Multi-layout Drone Camera** — SINGLE, PIP, SPLIT, QUAD layouts with EO/IR, SAR, SIGINT, and FUSION sensor modes
- **Prometheus metrics endpoint** (`/metrics`) for monitoring tick duration, connected clients, detection events, and HITL decisions
- **TLS/SSL support** for secure WebSocket connections with configurable certificates
- **Physics-based simulation** with 10 enemy unit types, 11 UAV flight modes, and fuel/endurance modeling
- **3 Theater configurations** (Romania, South China Sea, Baltic) with YAML scenario definition
- **Real-time Cesium 3D globe** with WebSocket-driven 10 Hz updates, entity labels, range rings, lock indicators, and 5 map layer overlays
- **React + Vite frontend** with Blueprint dark theme, resizable sidebar, and 4 sidebar tabs
- **1811 pytest tests** across 35 test files

---

## Quick Start

### Prerequisites

- **Python 3.10+** with venv
- **Node.js 18+** (for the React dashboard)
- **Web browser** (Chrome / Safari / Firefox)

### Setup

```bash
# Clone and enter project
git clone <repo-url> && cd Palantir

# Python dependencies
python -m venv venv
# Activate venv:
#   Windows: .\venv\Scripts\activate
#   macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

# Node dependencies (React dashboard)
cd src/frontend-react && npm install && cd ../..

# Copy environment config (optional — runs without API keys)
cp .env.example .env
```

---

## Startup Options

### Recommended: Unified Launcher

```bash
./palantir.sh
```

Starts the FastAPI backend (`:8000`), React dashboard (`:3000`), optional drone simulator, and opens your browser.

#### All Launcher Flags

```bash
./palantir.sh [--demo] [--no-sim] [--no-browser]
```

| Flag | Description |
|------|-------------|
| *(none)* | Standard interactive mode — HITL approval required for all strikes |
| `--demo` | Demo auto-pilot — full F2T2EA kill chain runs automatically, no human input |
| `--no-sim` | Skip the drone video simulator (use if OpenCV is not installed) |
| `--no-browser` | Don't open the browser automatically |

#### Common Startup Combinations

```bash
# Normal operation — manual HITL approval
./palantir.sh

# Watch the full kill chain run on its own
./palantir.sh --demo

# Demo without the video simulator (lighter)
./palantir.sh --demo --no-sim

# Headless (CI / server) — no browser pop
./palantir.sh --no-browser

# Fastest startup — no sim, no browser
./palantir.sh --no-sim --no-browser
```

### Run Components Individually

If you want to start services separately (useful for development):

```bash
# Terminal 1: Backend API server on :8000
.\venv\Scripts\python src/python/api_main.py          # Windows
# ./venv/bin/python src/python/api_main.py             # macOS/Linux

# Terminal 1 (demo mode):
$env:DEMO_MODE="true"; .\venv\Scripts\python src/python/api_main.py   # PowerShell
# DEMO_MODE=true ./venv/bin/python src/python/api_main.py              # bash

# Terminal 2: React dashboard (Vite dev server on :3000)
cd src/frontend-react && npm run dev
# Port 3000 is configured in vite.config.ts — no extra flags needed

# Terminal 3 (optional): Drone video simulator (requires OpenCV)
.\venv\Scripts\python src/python/vision/video_simulator.py

# Build the React dashboard for production
cd src/frontend-react && npm run build
```

Then open **http://localhost:3000** in your browser. No API keys needed — all agents run in heuristic mode by default.

### Run Tests

```bash
# All Python tests
python -m pytest src/python/tests/

# Single test file
python -m pytest src/python/tests/test_sim_integration.py

# With output (1811 tests across 35 test files)
python -m pytest src/python/tests/ -v
```

---

## Demo Mode

Run the full F2T2EA kill chain entirely on auto-pilot:

```bash
./palantir.sh --demo
```

What the auto-pilot does:
1. UAVs autonomously search assigned zones for targets
2. ISR Observer + Strategy Analyst detect and score targets
3. Nominations appear on the Strike Board automatically
4. **Auto-approves** nominations after a 5 s delay
5. Tactical Planner generates 3 Course of Action (COA) options
6. **Auto-authorizes** the highest-scored COA after a 3 s delay
7. Simulates engagement with probabilistic hit/kill outcomes
8. Updates target state (`DESTROYED` / `DAMAGED` / `ESCAPED`)
9. AI agent messages stream in real time to the Tactical AIP Assistant feed

A red `DEMO MODE` banner with a pulsing indicator appears at the top of the dashboard. No API keys are required — all agents run in heuristic mode.

> **To test manual HITL approval**: run without `--demo`. The kill chain will still run but nominations stop at the Strike Board and wait for your APPROVE / REJECT / AUTHORIZE actions.

---

## Target Verification Pipeline

Before a target can be nominated for engagement, it must pass through a multi-stage verification pipeline. This prevents false positives from reaching the kill chain.

### Verification States

```
DETECTED → CLASSIFIED → VERIFIED → NOMINATED
```

| State | Meaning | Advance Condition |
|-------|---------|-------------------|
| **DETECTED** | Initial sensor contact | `fused_confidence >= classify_confidence` threshold |
| **CLASSIFIED** | Target type confirmed | `fused_confidence >= verify_confidence` AND (`sensor_count >= 2` OR `time_in_state >= sustained_sec`) |
| **VERIFIED** | Multi-source corroboration | ISR pipeline picks up target for nomination |
| **NOMINATED** | Awaiting HITL approval on Strike Board | Operator approves or rejects |

### Per-Target-Type Thresholds

High-threat targets (SAM, TEL, MANPADS) verify faster with lower confidence thresholds. Low-priority targets (TRUCK, LOGISTICS, APC) require higher confidence and longer sustained observation.

| Type | Classify | Verify | Min Sensors | Sustained (s) | Regression (s) |
|------|----------|--------|-------------|----------------|-----------------|
| SAM | 0.50 | 0.70 | 2 | 10 | 8 |
| TEL | 0.50 | 0.70 | 2 | 10 | 10 |
| MANPADS | 0.50 | 0.70 | 2 | 10 | 8 |
| RADAR | 0.55 | 0.75 | 2 | 12 | 10 |
| C2_NODE | 0.55 | 0.75 | 2 | 12 | 10 |
| ARTILLERY | 0.55 | 0.75 | 2 | 12 | 10 |
| CP | 0.60 | 0.80 | 2 | 15 | 15 |
| TRUCK | 0.60 | 0.80 | 2 | 15 | 15 |
| LOGISTICS | 0.60 | 0.80 | 2 | 15 | 15 |
| APC | 0.60 | 0.80 | 2 | 15 | 15 |

### Regression

If no sensors observe a target for `regression_timeout_sec`, the target regresses one verification state (e.g., CLASSIFIED → DETECTED). This prevents stale verifications from lingering.

### Manual Override

Operators can manually fast-track a CLASSIFIED target to VERIFIED by clicking the **VERIFY** button on the enemy card (sends `verify_target` WebSocket action). This is useful when human intelligence confirms the target outside the automated pipeline.

### Demo Fast Mode

When `DEMO_MODE=true`, all thresholds are halved (times) and lowered (confidence −0.1), allowing the verification pipeline to advance rapidly for demonstration purposes.

### UI Components

- **VerificationStepper** — color-coded dot stepper on each enemy card showing DETECTED → CLASSIFIED → VERIFIED → NOMINATED progression with a confidence progress bar
- **FusionBar** — stacked bar chart showing per-sensor-type confidence contributions (EO/IR blue, SAR green, SIGINT orange)
- **SensorBadge** — badge showing how many distinct sensor types are observing the target (color-coded: 1=neutral, 2=warning, 3+=success)

---

## Swarm Coordination

The swarm coordinator (`swarm_coordinator.py`) manages multi-UAV tasking:

- **Greedy assignment** — assigns available UAVs to highest-priority targets first
- **Sensor-gap detection** — identifies targets missing EO/IR, SAR, or SIGINT coverage
- **Priority scoring** — threat weight × verification gap × sensor coverage need
- **Task expiry** — 120-second TTL on swarm assignments, auto-release on target state transitions
- **Idle guard** — ensures minimum UAV availability for new detections
- **Formation types** — sensor assignments based on target type and available UAV sensors

### Swarm UI

- **SwarmPanel** — per-target sensor coverage visualization with assigned UAV list
- **Swarm Lines** — Cesium polylines connecting swarm-assigned UAVs to their targets
- **SWARM map mode** (key: 5) — highlights swarm formations and task assignments

---

## Battlespace Assessment

The assessment engine (`battlespace_assessment.py`) provides real-time tactical intelligence:

- **Threat Clustering** — groups nearby targets into clusters (SAM_BATTERY, CONVOY, CP_COMPLEX, AD_NETWORK, MIXED) using distance-based affinity
- **Coverage Gap Detection** — identifies grid zones with no UAV coverage
- **Zone Threat Scoring** — per-zone threat level based on target types and count
- **Movement Corridor Detection** — tracks target movement patterns over time

### Assessment UI (ASSESS Tab)

- **ThreatClusterCard** — cluster type, member count, threat score
- **CoverageGapAlert** — list of uncovered zones requiring attention
- **ZoneThreatHeatmap** — color-coded zone threat levels

---

## ISR Priority Queue

The ISR priority engine (`isr_priority.py`) ranks targets for sensor retasking:

- **Urgency scoring** — threat weight × (1 − verification progress) × sensor gap multiplier
- **Verification gap** — distance from current confidence to next threshold
- **Missing sensor detection** — identifies which sensor types a target still needs
- **UAV recommendation** — suggests specific UAVs based on proximity and sensor loadout

### ISR Queue UI (MISSION Tab)

- **ISRQueue** — table of prioritized targets with urgency, gap, and recommended sensors

---

## Map Modes

Six map modes provide different tactical views. Switch with keyboard shortcuts or the MapModeBar overlay.

| Mode | Key | Description | Visible Layers |
|------|-----|-------------|----------------|
| **OPERATIONAL** | 1 | Default view — all assets and targets | Drones, targets, zones, flow lines |
| **COVERAGE** | 2 | Sensor coverage analysis | Drones, zones, coverage overlay |
| **THREAT** | 3 | Threat-focused view | Targets, threat overlay |
| **FUSION** | 4 | Sensor fusion confidence | Drones, targets, fusion overlay |
| **SWARM** | 5 | Swarm formations and tasking | Drones, targets, flow lines, swarm overlay |
| **TERRAIN** | 6 | Terrain analysis | Drones, targets, terrain overlay |

### Layer Controls

The **LayerPanel** (top-right of globe) allows toggling individual layers independently of the active map mode: drones, targets, zones, flow lines, coverage, threat, fusion, swarm, terrain.

---

## Enemy UAVs

The system detects and tracks adversary drones with four operational modes:

| Mode | Description |
|------|-------------|
| **RECON** | Reconnaissance — observing friendly positions |
| **ATTACK** | Offensive approach toward friendly assets |
| **JAMMING** | Electronic warfare — disrupting sensor feeds |
| **EVADING** | Attempting to escape tracking |

### Enemy UAV UI

- **EnemyUAVCard** — in ENEMIES tab, shows mode, confidence, sensor count
- **Cesium rendering** — enemy UAV entities on the globe via `useCesiumEnemyUAVs`
- **Intercept action** — `intercept_enemy` WebSocket command to task a friendly UAV

---

## Intel Feed System

The `IntelFeedRouter` (`intel_feed.py`) provides typed event streams:

| Feed | Content |
|------|---------|
| **INTEL_FEED** | Target state transitions, detections, verifications |
| **COMMAND_FEED** | Operator actions, mode changes, approvals |
| **SENSOR_FEED** | Sensor retasking, coverage updates |

Clients subscribe to specific feeds via the `subscribe` WebSocket action. Legacy clients receive all broadcasts.

### Feed UI (MISSION Tab)

- **IntelFeed** — scrolling feed of target state transitions with severity tags
- **CommandLog** — table of operator and AI actions with timestamps

---

## UAV Flight Modes

UAVs are commanded from the **ASSETS** tab drone cards or by clicking entities on the globe. FOLLOW, PAINT, and INTERCEPT require a target to be selected first.

### Mode Reference

| Mode | Button | Target Required | Description |
|------|--------|-----------------|-------------|
| **SEARCH** | Green | No | Area patrol — autonomous circular loiter over assigned zone |
| **FOLLOW** | Purple | Yes | Loose tracking — maintains visual contact at safe distance |
| **PAINT** | Red | Yes | Laser designation — tight orbit with active laser lock |
| **INTERCEPT** | Orange | Yes | Direct approach — flies straight at target at maximum speed |
| **SUPPORT** | — | Yes | Swarm support — sensor assist for a primary tracker |
| **VERIFY** | — | Yes | Verification pass — contributes sensor data for target verification |
| **OVERWATCH** | — | No | Elevated overwatch position above area of interest |
| **BDA** | — | Yes | Battle damage assessment — post-strike observation |
| **IDLE** | — | — | Stationary hold, no assignment |
| **REPOSITIONING** | — | — | Automatic rebalancing to an under-covered zone |
| **RTB** | — | — | Return to base — triggered automatically on low fuel |

### Autonomy Levels

| Level | Description |
|-------|-------------|
| **MANUAL** | All UAV commands require operator input |
| **SUPERVISED** | AI proposes mode transitions, operator approves/rejects |
| **AUTONOMOUS** | AI controls UAV tasking autonomously |

Per-UAV autonomy override is available. Pending transitions appear as toasts (`TransitionToast`) requiring operator approval in SUPERVISED mode.

### When to Use Each Mode

#### SEARCH
Send a UAV into SEARCH when you want it to autonomously scan its assigned grid zone. The UAV executes a constant-radius circular loiter, maximizing sensor coverage. Use SEARCH to release a UAV from a target assignment and return it to area patrol.

```
Use for: area reconnaissance, zone coverage, releasing from a target
Effect:  UAV enters circular loiter over zone center
```

#### FOLLOW
FOLLOW puts a UAV into a loose ~2 km orbit around the selected target. The UAV maintains visual contact without committing to a weapons-capable engagement geometry. Target state is **not** set to LOCKED — this is a surveillance mode, not a designation mode.

```
Use for: persistent surveillance, keeping eyes on a target of interest,
         cueing other UAVs or passing targeting data downstream
Effect:  UAV orbits ~2 km from target, smooth fixed-wing arcs
         Target stays in DETECTED/TRACKED state (not LOCKED)
```

#### PAINT
PAINT commands a tight ~1 km laser-designation orbit. The UAV flies close enough to maintain a **laser lock** on the target, setting its state to `LOCKED`. This is a prerequisite for weapons authorization — the Tactical Planner will generate COAs once a target is LOCKED. If a strike is authorized, the effector requires an active PAINT UAV to guide the weapon to impact.

```
Use for: marking a target for strike, enabling weapons authorization
Effect:  UAV orbits ~1 km from target
         Target state → LOCKED
         Strike Board nominations become authorizable
         Drone cam shows pulsing red lock box
```

#### INTERCEPT
INTERCEPT sends the UAV on a direct heading toward the target at **1.5x normal speed**. It is the fastest way to close distance to a target — useful when a high-priority target is detected at range and needs to be engaged immediately, or when you want to force a mobile target to stop maneuvering. The UAV transitions to a ~300 m danger-close orbit and also sets target state to `LOCKED`.

```
Use for: high-priority time-sensitive targets, forcing engagement on mobile units,
         rapid response when a target is about to leave sensor range
Effect:  UAV flies direct at 1.5x speed, then orbits ~300 m from target
         Target state → LOCKED (same as PAINT but with aggressive approach)
         High risk — danger-close orbit means UAV is within SAM/MANPADS range
```

#### PAINT vs INTERCEPT — Tactical Decision

| Factor | PAINT | INTERCEPT |
|--------|-------|-----------|
| Approach | Already in orbit | Direct dash from current position |
| Orbit radius | ~1 km | ~300 m |
| Speed | Normal | 1.5x normal |
| Risk to UAV | Low-medium | High (within SAM envelope) |
| Time to lock | Immediate (if nearby) | Faster (if far away) |
| Best for | Deliberate strikes on known targets | Time-sensitive / fleeing targets |

> **Tip:** For a stationary high-value target, use PAINT — it keeps the UAV at a survivable standoff while maintaining laser lock. For a mobile target that's about to disappear (TEL relocating, truck fleeing), use INTERCEPT to close the distance fast before it escapes.

---

## Interface Guide

### Sidebar Tabs

**MISSION** — Theater selector, Tactical AIP Assistant message feed, Intel Feed, Command Log, ISR Queue, Strike Board, Grid Controls, Autonomy Toggle, Coverage Mode Toggle.

**ASSETS** — Drone cards for each active UAV. Click a card to expand it and activate the drone camera PIP. Expanded card shows:
- Altitude, sensor type, tracking assignment, coordinates
- Mode command buttons (SEARCH / FOLLOW / PAINT / INTERCEPT)
- Set Waypoint toggle (then click on the globe to place a waypoint)
- Autonomy override and mode source indicators
- Pending transition approval (in SUPERVISED mode)

**ENEMIES** — Enemy target cards for all detected contacts. Shows type badge, target ID, state badge, tracking UAV tags with mode colors, coordinates, and detection confidence. Click a card to select the target (required before commanding FOLLOW / PAINT / INTERCEPT). Also shows enemy UAV cards with mode and confidence indicators.

**ASSESS** — Battlespace assessment dashboard with threat cluster cards, coverage gap alerts, and zone threat heatmap.

### Strike Board (MISSION tab)

The strike board is the HITL approval interface. Two gates:

1. **Nomination** — ISR + Strategy Analyst proposes a target. Operator selects **APPROVE** or **REJECT**.
2. **COA Authorization** — Tactical Planner generates 3 courses of action. Operator selects which COA to **AUTHORIZE**.

After authorization, the Effectors Agent executes the strike and reports BDA (Battle Damage Assessment).

### Drone Camera PIP

The drone camera system supports **4 layouts** selectable via the `CamLayoutSelector`:

| Layout | Description |
|--------|-------------|
| **SINGLE** | One full-size camera feed |
| **PIP** | Main feed with small picture-in-picture overlay |
| **SPLIT** | Two side-by-side camera feeds |
| **QUAD** | Four simultaneous camera feeds |

Each camera slot supports **4 sensor modes**:

| Mode | Description |
|------|-------------|
| **EO/IR** | Electro-optical / infrared — standard visual camera |
| **SAR** | Synthetic aperture radar — all-weather ground mapping |
| **SIGINT** | Signals intelligence — RF emission detection and spectrum display |
| **FUSION** | Combined multi-sensor overlay |

The canvas renders:
- Target symbols with type-specific shapes (diamond=TEL, triangle=SAM, square=TRUCK, etc.)
- Detection confidence percentage per target
- HUD: drone ID, altitude, heading, mode, coordinates
- Tracking reticle and range/bearing readouts when in FOLLOW/PAINT/INTERCEPT
- Pulsing red lock box when in PAINT mode with active laser designation
- **SensorHUD** overlay with sensor-specific telemetry
- **SigintDisplay** for RF spectrum waterfall visualization
- **CameraPresets** overlay (OVERVIEW, TOP DOWN, OBLIQUE, FREE)

Click any drone card in the ASSETS tab to activate a camera slot. Click again to deselect.

### Globe Interactions

- **Single-click drone entity** → select drone (macro camera follow)
- **Double-click drone entity** → third-person camera lock-on
- **Single-click target entity** → select target
- **Double-click empty space** → spike (triggers threat response simulation)
- **Set Waypoint active + click globe** → sends waypoint to selected drone
- **Camera controls** (top-left when drone tracked): Globe icon returns to theater view; X decouples camera
- **MapModeBar** (top of globe): switch between 6 map modes or press 1-6
- **LayerPanel** (top-right): toggle individual map layers

---

## Architecture

```
src/
  python/
    api_main.py              # FastAPI server, WebSocket hub, agent pipeline, demo autopilot
    sim_engine.py            # Physics simulation (UAVs, targets, zones, red force AI)
    verification_engine.py   # Target verification state machine (DETECTED→CLASSIFIED→VERIFIED→NOMINATED)
    sensor_fusion.py         # Multi-sensor complementary fusion (1 - product(1-ci)) with dedup
    sensor_model.py          # Probabilistic detection model (Pd, RCS, weather)
    swarm_coordinator.py     # Greedy UAV-to-target assignment with sensor-gap detection
    battlespace_assessment.py # Threat clustering, coverage gaps, zone scoring, corridors
    isr_priority.py          # ISR priority queue builder — urgency scoring + UAV recommendation
    intel_feed.py            # Subscription-filtered event broadcast (INTEL, COMMAND, SENSOR feeds)
    pipeline.py              # F2T2EA kill chain orchestrator
    config.py                # Pydantic-settings env var management
    hitl_manager.py          # Two-gate HITL approval system
    theater_loader.py        # YAML theater configuration loader
    llm_adapter.py           # Multi-provider LLM fallback (Gemini → Anthropic → heuristic)
    event_logger.py          # Structured event logging (async JSONL with daily rotation)
    websocket_manager.py     # WebSocket connection lifecycle management
    logging_config.py        # Structured logging configuration (structlog)
    core/
      ontology.py            # Pydantic data models — shared data contract for all agents
      state.py               # LangGraph state with annotated reducers
    agents/
      isr_observer.py        # Find / Fix / Track — sensor fusion
      strategy_analyst.py    # Target — ROE evaluation + priority scoring
      tactical_planner.py    # Engage — COA generation
      effectors_agent.py     # Assess — execution + BDA
      pattern_analyzer.py    # Activity pattern analysis
      ai_tasking_manager.py  # Sensor retasking optimization
      battlespace_manager.py # Map layers + threat ring management
      synthesis_query_agent.py # SITREP generation
      performance_auditor.py # System performance monitoring
    data/
      historical_activity.py # Historical pattern data
    mission_data/
      asset_registry.py      # UAV and effector asset definitions
      historical_activity.py # Mission-specific activity history
    utils/
      geo_utils.py           # Geospatial calculation utilities
    vision/
      video_simulator.py     # Drone camera video simulator (OpenCV)
      vision_processor.py    # Video frame analysis
      coordinate_transformer.py # Geo ↔ pixel coordinate transform
      dashboard_connector.py # Vision pipeline → dashboard bridge
    tests/                   # 1811 pytest tests (35 test files)
  frontend-react/            # React + Vite dashboard (primary)
    src/
      App.tsx                # Root layout — sidebar + globe + overlays
      main.tsx               # Entry point — Blueprint theme, Zustand store, ECharts theme
      store/
        SimulationStore.ts   # Zustand store — simulation state + UI state
        types.ts             # TypeScript types (UAV, Target, Zone, StrikeEntry, COA, Assessment…)
      hooks/
        useWebSocket.ts      # WebSocket connection, reconnect, message routing
        useDroneCam.ts       # Canvas render loop — synthetic drone camera feed
        useSensorCanvas.ts   # Sensor-specific canvas renderer (EO/IR, SAR, SIGINT, FUSION)
        useCesiumViewer.ts   # Cesium viewer lifecycle hook
        useResizable.ts      # Resizable sidebar hook
      cesium/
        CesiumContainer.tsx  # Cesium Viewer lifecycle, wires all Cesium hooks + layer overlays
        useCesiumDrones.ts   # UAV 3D entity rendering with mode-colored labels
        useCesiumTargets.ts  # Target entity rendering with type/ID labels + threat rings
        useCesiumZones.ts    # Grid zone visualization
        useCesiumFlowLines.ts # Asset-to-target flow line overlays
        useCesiumCompass.ts  # Compass needle + ring following tracked drone
        useCesiumMacroTrack.ts # Smooth camera follow (macro mode)
        useCesiumClickHandlers.ts # Entity picking, waypoint placement, spike
        useCesiumRangeRings.ts # Sensor range ring overlays
        useCesiumWaypoints.ts  # Waypoint cylinders + trajectory polylines
        useCesiumLockIndicators.ts # Red pulsing lock ring on PAINT targets
        useCesiumAssessment.ts # Assessment visualization (clusters, gaps, corridors)
        useCesiumEnemyUAVs.ts # Enemy UAV entity rendering
        useCesiumSwarmLines.ts # Swarm coordination polylines
        CameraControls.tsx   # Globe-return + camera decouple buttons
        DetailMapDialog.tsx  # Precision waypoint placement modal
        layers/
          useCoverageLayer.ts  # Sensor coverage heatmap overlay
          useFusionLayer.ts    # Fusion confidence visualization
          useSwarmLayer.ts     # Swarm formation overlay
          useThreatLayer.ts    # Threat density overlay
          useTerrainLayer.ts   # Terrain analysis overlay
      panels/
        Sidebar.tsx          # Resizable sidebar container
        SidebarTabs.tsx      # MISSION / ASSETS / ENEMIES / ASSESS tab navigation
        mission/             # MISSION tab components
          MissionTab.tsx     # Theater selector + assistant + feeds + strike board
          TheaterSelector.tsx
          AssistantWidget.tsx
          StrikeBoard.tsx
          StrikeBoardEntry.tsx
          StrikeBoardCoa.tsx
          GridControls.tsx
          AutonomyToggle.tsx   # MANUAL / SUPERVISED / AUTONOMOUS selector
          CoverageModeToggle.tsx # balanced / threat_adaptive toggle
          ISRQueue.tsx         # Prioritized ISR requirements table
          IntelFeed.tsx        # Target state transition feed
          CommandLog.tsx       # Operator action history
        assets/              # ASSETS tab — drone management
          AssetsTab.tsx
          DroneCard.tsx      # Drone card with mode tag + drone cam activation
          DroneCardDetails.tsx
          DroneModeButtons.tsx  # SEARCH / FOLLOW / PAINT / INTERCEPT buttons
          DroneActionButtons.tsx
          TransitionToast.tsx   # Autonomy transition approval toast
        enemies/             # ENEMIES tab — threat tracking + verification
          EnemiesTab.tsx
          ThreatSummary.tsx
          EnemyCard.tsx
          EnemyUAVCard.tsx     # Adversary drone card
          SwarmPanel.tsx       # Per-target swarm sensor coverage
          VerificationStepper.tsx  # 4-step verification progress dots + confidence bar
          FusionBar.tsx            # Stacked sensor contribution bar chart (ECharts)
          SensorBadge.tsx          # Multi-sensor count badge with intent color
        assessment/          # ASSESS tab — battlespace intelligence
          AssessmentTab.tsx
          ThreatClusterCard.tsx
          CoverageGapAlert.tsx
          ZoneThreatHeatmap.tsx
      overlays/
        DroneCamPIP.tsx      # Multi-layout drone camera orchestrator (SINGLE/PIP/SPLIT/QUAD)
        DemoBanner.tsx       # Demo mode indicator strip
        MapModeBar.tsx       # 6-mode tactical view selector (keyboard 1-6)
        LayerPanel.tsx       # Per-layer visibility toggles
        CameraPresets.tsx    # Camera angle presets (OVERVIEW/TOP DOWN/OBLIQUE/FREE)
      components/
        CamLayoutSelector.tsx  # Camera layout picker (SINGLE/PIP/SPLIT/QUAD)
        SensorHUD.tsx          # Per-sensor telemetry overlay
        SigintDisplay.tsx      # SIGINT RF spectrum waterfall display
      shared/
        constants.ts         # Mode styles, target map, sensor constants
        geo.ts               # Haversine distance, bearing helpers
        api.ts               # WebSocket message builder
      theme/
        palantir.ts          # ECharts Palantir dark theme
  frontend/                  # Legacy vanilla JS frontend (reference only)
theaters/
  romania.yaml               # Default theater — Black Sea / Romania
  south_china_sea.yaml       # Pacific theater
  baltic.yaml                # Baltic theater
```

### AI Agent Pipeline

```
ISR Observer → Strategy Analyst → [HITL Gate 1: Nomination] → Tactical Planner → [HITL Gate 2: COA Auth] → Effectors Agent
```

**9 agents** in total:

| Agent | Role |
|-------|------|
| ISR Observer | Find / Fix / Track — sensor fusion and target classification |
| Strategy Analyst | ROE evaluation, priority scoring, nomination |
| Tactical Planner | Course of Action (COA) generation |
| Effectors Agent | Strike execution and Battle Damage Assessment |
| Pattern Analyzer | Activity pattern analysis across targets |
| AI Tasking Manager | Sensor retasking optimization |
| Battlespace Manager | Map layers, threat ring management |
| Synthesis Query Agent | SITREP generation and natural language queries |
| Performance Auditor | System performance monitoring |

Each agent runs in **heuristic mode** by default (no API keys needed). When LLM keys are configured in `.env`, agents upgrade to LLM-backed reasoning via the multi-provider fallback chain (Gemini → Anthropic → Ollama → heuristic).

### Simulation Engine

The sim engine models:
- **UAVs**: 11 operational modes with fixed-wing physics, fuel consumption, multi-sensor loadouts, and zone-based coverage optimization
- **Targets**: 10 unit types (`SAM`, `TEL`, `TRUCK`, `CP`, `MANPADS`, `RADAR`, `C2_NODE`, `LOGISTICS`, `ARTILLERY`, `APC`) with type-specific behaviors (patrol, ambush, shoot-and-scoot, concealment, flee)
- **Enemy UAVs**: Adversary drones with RECON, ATTACK, JAMMING, EVADING modes
- **Environment**: Time of day, cloud cover, precipitation affecting sensor performance
- **Detection**: Probabilistic Pd model incorporating range, RCS, and weather penalties
- **Swarm Coordination**: Greedy assignment with sensor-gap detection and priority-weighted tasking
- **Battlespace Assessment**: Real-time threat clustering, coverage analysis, and movement corridor detection

---

## WebSocket Protocol

Backend broadcasts full simulation state as JSON at 10 Hz. All messages include a `type` field.

**Server → Client:**
| Type | Description |
|------|-------------|
| `state` | Full sim state — drones, targets, zones, flows, strike board, assessment, ISR queue, enemy UAVs, swarm tasks |
| `ASSISTANT_MESSAGE` | AI agent notification with severity (INFO / WARNING / CRITICAL) |
| `HITL_UPDATE` | Strike board nomination or COA status change |
| `SITREP_RESPONSE` | Situation report query result |
| `INTEL_FEED` | Target state transition event |
| `COMMAND_FEED` | Operator/AI action event |
| `SENSOR_FEED` | Sensor retasking event |
| `ERROR` | Validation or rate-limit error |

**Client → Server actions:**
| Action | Fields | Description |
|--------|--------|-------------|
| `scan_area` | `drone_id` | Command UAV to SEARCH mode |
| `follow_target` | `drone_id`, `target_id` | Command FOLLOW mode |
| `paint_target` | `drone_id`, `target_id` | Command PAINT (laser lock) |
| `intercept_target` | `drone_id`, `target_id` | Command INTERCEPT |
| `intercept_enemy` | `drone_id`, `enemy_uav_id` | Intercept an enemy UAV |
| `cancel_track` | `drone_id` | Release from target |
| `move_drone` | `drone_id`, `target_lon`, `target_lat` | Set waypoint |
| `spike` | `lon`, `lat` | Trigger threat response at location |
| `approve_nomination` | `entry_id` | HITL Gate 1 — approve |
| `reject_nomination` | `entry_id` | HITL Gate 1 — reject |
| `retask_nomination` | `entry_id` | Retask nomination for re-evaluation |
| `authorize_coa` | `entry_id`, `coa_id` | HITL Gate 2 — authorize |
| `reject_coa` | `entry_id`, `coa_id` | HITL Gate 2 — reject COA |
| `sitrep_query` | `query` | Request situation report |
| `verify_target` | `target_id` | Manual fast-track CLASSIFIED → VERIFIED |
| `retask_sensors` | `zone_id` | Retask sensors to zone |
| `set_autonomy_level` | `level` | Set global autonomy (MANUAL/SUPERVISED/AUTONOMOUS) |
| `set_drone_autonomy` | `drone_id`, `level` | Set per-drone autonomy override |
| `approve_transition` | `drone_id` | Approve pending autonomy transition |
| `reject_transition` | `drone_id` | Reject pending autonomy transition |
| `request_swarm` | `target_id` | Request swarm assignment for target |
| `release_swarm` | `target_id` | Release swarm from target |
| `set_coverage_mode` | `mode` | Set coverage mode (balanced/threat_adaptive) |
| `subscribe` | `feeds` | Subscribe to specific feed types |
| `subscribe_sensor_feed` | `drone_id` | Subscribe to real-time sensor data |
| `reset` | — | Reset simulation state |
| `SET_SCENARIO` | `theater` | Switch active theater |

For complete AsyncAPI schema and WebSocket protocol documentation, see `asyncapi.yaml` and `websocket_protocol.md`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/ws` | WebSocket — 10 Hz sim state + bidirectional commands |
| GET | `/metrics` | Prometheus text-format metrics (tick duration, clients, events) |
| POST | `/api/sitrep` | Generate situation report |
| POST | `/api/environment` | Set weather / time conditions |
| GET | `/api/theaters` | List available theaters |
| POST | `/api/theater` | Switch active theater |
| GET | `/docs` | FastAPI Swagger UI |

---

## Environment Variables

The system runs fully in heuristic mode without any API keys. Keys unlock LLM-backed agent reasoning.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (empty) | OpenAI API key (optional) |
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API key (optional) |
| `GEMINI_API_KEY` | (empty) | Google Gemini API key (optional) |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `SIMULATION_HZ` | `10` | Simulation tick rate |
| `DEFAULT_THEATER` | `romania` | Default theater on startup |
| `DEMO_MODE` | `false` | Enable demo auto-pilot (or use `--demo` flag) |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `WS_BACKEND_URL` | `ws://localhost:8000/ws` | WebSocket URL for simulator clients |
| `SSL_ENABLED` | `false` | Enable TLS/SSL for WebSocket connections |
| `SSL_CERTFILE` | (empty) | Path to PEM certificate file (required if `SSL_ENABLED=true`) |
| `SSL_KEYFILE` | (empty) | Path to PEM private key file (required if `SSL_ENABLED=true`) |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Comma-separated WebSocket origin allowlist |

---

## Contributing

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Write tests first: `python -m pytest src/python/tests/`
3. Commit: `git commit -m "feat: description"`
4. Open a PR

---

## License

MIT — see [LICENSE](LICENSE) for details.
