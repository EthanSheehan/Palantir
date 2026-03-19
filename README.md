# Palantir C2 — Multi-Agent Decision-Centric Command & Control

![Project Status](https://img.shields.io/badge/status-active-success.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Overview

**Palantir C2** is a high-fidelity Command and Control system that automates the **F2T2EA kill chain** (Find, Fix, Track, Target, Engage, Assess) using multi-agent AI orchestration, a physics-based tactical simulator, and a Cesium 3D geospatial frontend.

- **8 AI Agents** orchestrating the full kill chain with heuristic + LLM fallback
- **Human-in-the-Loop (HITL)** two-gate approval system for strike authorization
- **Physics-based simulation** with 10 enemy unit types, 7 UAV flight modes, and fuel/endurance modeling
- **3 Theater configurations** (Romania, South China Sea, Baltic) with YAML scenario definition
- **Real-time Cesium 3D globe** with WebSocket-driven 10 Hz updates, entity labels, range rings, and lock indicators
- **React + Vite frontend** with Blueprint dark theme, resizable sidebar, and synthetic drone camera PIP

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
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

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
# Backend API server on :8000
./venv/bin/python3 src/python/api_main.py

# Backend with demo auto-pilot enabled
DEMO_MODE=true ./venv/bin/python3 src/python/api_main.py

# React dashboard (Vite dev server on :3000)
cd src/frontend-react && npm run dev -- --port 3000

# Drone video simulator (requires OpenCV)
./venv/bin/python3 src/python/vision/video_simulator.py

# Build the React dashboard for production
cd src/frontend-react && npm run build
```

### Run Tests

```bash
# All Python tests
./venv/bin/python3 -m pytest src/python/tests/

# Single test file
./venv/bin/python3 -m pytest src/python/tests/test_sim_integration.py

# With output
./venv/bin/python3 -m pytest src/python/tests/ -v
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

## UAV Flight Modes

UAVs are commanded from the **ASSETS** tab drone cards or by clicking entities on the globe. FOLLOW, PAINT, and INTERCEPT require a target to be selected first (click a target card in the ENEMIES tab or click the target on the globe).

### Mode Reference

| Mode | Button | Target Required | Description |
|------|--------|-----------------|-------------|
| **SEARCH** | Green | No | Area patrol — autonomous circular loiter over assigned zone |
| **FOLLOW** | Purple | Yes | Loose tracking — maintains visual contact at safe distance |
| **PAINT** | Red | Yes | Laser designation — tight orbit with active laser lock |
| **INTERCEPT** | Orange | Yes | Direct approach — flies straight at target at maximum speed |
| **IDLE** | — | — | Stationary hold, no assignment |
| **REPOSITIONING** | — | — | Automatic rebalancing to an under-covered zone |
| **RTB** | — | — | Return to base — triggered automatically on low fuel |

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
INTERCEPT sends the UAV on a direct heading toward the target at **1.5× normal speed**. It is the fastest way to close distance to a target — useful when a high-priority target is detected at range and needs to be engaged immediately, or when you want to force a mobile target to stop maneuvering. The UAV transitions to a ~300 m danger-close orbit and also sets target state to `LOCKED`.

```
Use for: high-priority time-sensitive targets, forcing engagement on mobile units,
         rapid response when a target is about to leave sensor range
Effect:  UAV flies direct at 1.5× speed, then orbits ~300 m from target
         Target state → LOCKED (same as PAINT but with aggressive approach)
         High risk — danger-close orbit means UAV is within SAM/MANPADS range
```

#### PAINT vs INTERCEPT — Tactical Decision

| Factor | PAINT | INTERCEPT |
|--------|-------|-----------|
| Approach | Already in orbit | Direct dash from current position |
| Orbit radius | ~1 km | ~300 m |
| Speed | Normal | 1.5× normal |
| Risk to UAV | Low–medium | High (within SAM envelope) |
| Time to lock | Immediate (if nearby) | Faster (if far away) |
| Best for | Deliberate strikes on known targets | Time-sensitive / fleeing targets |

> **Tip:** For a stationary high-value target, use PAINT — it keeps the UAV at a survivable standoff while maintaining laser lock. For a mobile target that's about to disappear (TEL relocating, truck fleeing), use INTERCEPT to close the distance fast before it escapes.

---

## Interface Guide

### Sidebar Tabs

**MISSION** — Theater selector, Tactical AIP Assistant message feed, Strike Board, grid controls.

**ASSETS** — Drone cards for each active UAV. Click a card to expand it and activate the drone camera PIP. Expanded card shows:
- Altitude, sensor type, tracking assignment, coordinates
- Mode command buttons (SEARCH / FOLLOW / PAINT / INTERCEPT)
- Set Waypoint toggle (then click on the globe to place a waypoint)

**ENEMIES** — Enemy target cards for all detected contacts. Shows type badge, target ID, state badge, tracking UAV tags with mode colors, coordinates, and detection confidence. Click a card to select the target (required before commanding FOLLOW / PAINT / INTERCEPT).

### Strike Board (MISSION tab)

The strike board is the HITL approval interface. Two gates:

1. **Nomination** — ISR + Strategy Analyst proposes a target. Operator selects **APPROVE** or **REJECT**.
2. **COA Authorization** — Tactical Planner generates 3 courses of action. Operator selects which COA to **AUTHORIZE**.

After authorization, the Effectors Agent executes the strike and reports BDA (Battle Damage Assessment).

### Drone Camera PIP

Click any drone card in the ASSETS tab to activate the synthetic drone camera feed (bottom-right of the globe). The canvas renders:
- Target symbols with type-specific shapes (diamond=TEL, triangle=SAM, square=TRUCK, etc.)
- Detection confidence percentage per target
- HUD: drone ID, altitude, heading, mode, coordinates
- Tracking reticle and range/bearing readouts when in FOLLOW/PAINT/INTERCEPT
- Pulsing red lock box when in PAINT mode with active laser designation

Click the card again to deselect and close the PIP.

### Globe Interactions

- **Single-click drone entity** → select drone (macro camera follow)
- **Double-click drone entity** → third-person camera lock-on
- **Single-click target entity** → select target
- **Double-click empty space** → spike (triggers threat response simulation)
- **Set Waypoint active + click globe** → sends waypoint to selected drone
- **Camera controls** (top-left when drone tracked): Globe icon returns to theater view; X decouples camera

---

## Architecture

```
src/
  python/
    api_main.py              # FastAPI server, WebSocket hub, agent pipeline, demo autopilot
    sim_engine.py            # Physics simulation (UAVs, targets, zones, red force AI)
    pipeline.py              # F2T2EA kill chain orchestrator
    config.py                # Pydantic-settings env var management
    hitl_manager.py          # Two-gate HITL approval system
    theater_loader.py        # YAML theater configuration loader
    llm_adapter.py           # Multi-provider LLM fallback (Gemini → Anthropic → heuristic)
    sensor_model.py          # Probabilistic detection model (Pd, RCS, weather)
    event_logger.py          # Structured event logging
    agents/
      isr_observer.py        # Find / Fix / Track — sensor fusion
      strategy_analyst.py    # Target — ROE evaluation + priority scoring
      tactical_planner.py    # Engage — COA generation
      effectors_agent.py     # Assess — execution + BDA
      pattern_analyzer.py    # Activity pattern analysis
      ai_tasking_manager.py  # Sensor retasking optimization
      battlespace_manager.py # Map layers + threat ring management
      synthesis_query_agent.py # SITREP generation
    tests/                   # 214+ pytest tests
  frontend-react/            # React + Vite dashboard (primary)
    src/
      App.tsx                # Root layout — sidebar + globe + overlays
      main.tsx               # Entry point — Blueprint theme, Zustand store, ECharts theme
      store/
        SimulationStore.ts   # Zustand store — simulation state + UI state
        types.ts             # TypeScript types (UAV, Target, Zone, StrikeEntry, COA…)
      hooks/
        useWebSocket.ts      # WebSocket connection, reconnect, message routing
        useDroneCam.ts       # Canvas render loop — synthetic drone camera feed
        useResizable.ts      # Resizable sidebar hook
      cesium/
        CesiumContainer.tsx  # Cesium Viewer lifecycle, wires all Cesium hooks
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
        CameraControls.tsx   # Globe-return + camera decouple buttons
        DetailMapDialog.tsx  # Precision waypoint placement modal
      panels/
        Sidebar.tsx          # Resizable sidebar container
        SidebarTabs.tsx      # MISSION / ASSETS / ENEMIES tab navigation
        mission/             # MISSION tab components
          MissionTab.tsx     # Theater selector + assistant widget + strike board
          TheaterSelector.tsx
          AssistantWidget.tsx
          StrikeBoard.tsx
          StrikeBoardEntry.tsx
          StrikeBoardCoa.tsx
          GridControls.tsx
        assets/              # ASSETS tab — drone management
          AssetsTab.tsx
          DroneCard.tsx      # Drone card with mode tag + drone cam activation
          DroneCardDetails.tsx
          DroneModeButtons.tsx  # SEARCH / FOLLOW / PAINT / INTERCEPT buttons
          DroneActionButtons.tsx
        enemies/             # ENEMIES tab — threat tracking
          EnemiesTab.tsx
          ThreatSummary.tsx
          EnemyCard.tsx
      overlays/
        DroneCamPIP.tsx      # Synthetic drone camera picture-in-picture
        DemoBanner.tsx       # Demo mode indicator strip
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

Each agent runs in **heuristic mode** by default (no API keys needed). When LLM keys are configured in `.env`, agents upgrade to LLM-backed reasoning via the multi-provider fallback chain (Gemini → Anthropic → Ollama → heuristic).

### Simulation Engine

The sim engine models:
- **UAVs**: 7 operational modes with fixed-wing physics, fuel consumption, and zone-based coverage optimization
- **Targets**: 10 unit types (`SAM`, `TEL`, `TRUCK`, `CP`, `MANPADS`, `RADAR`, `C2_NODE`, `LOGISTICS`, `ARTILLERY`, `APC`) with type-specific behaviors (patrol, ambush, shoot-and-scoot, concealment, flee)
- **Environment**: Time of day, cloud cover, precipitation affecting sensor performance
- **Detection**: Probabilistic Pd model incorporating range, RCS, and weather penalties

---

## WebSocket Protocol

Backend broadcasts full simulation state as JSON at 10 Hz. All messages include a `type` field.

**Server → Client:**
| Type | Description |
|------|-------------|
| `state` | Full sim state — drones, targets, zones, flows, strike board, demo_mode flag |
| `ASSISTANT_MESSAGE` | AI agent notification with severity (INFO / WARNING / CRITICAL) |
| `HITL_UPDATE` | Strike board nomination or COA status change |
| `SITREP_RESPONSE` | Situation report query result |
| `ERROR` | Validation or rate-limit error |

**Client → Server actions:**
| Action | Fields | Description |
|--------|--------|-------------|
| `scan_area` | `drone_id` | Command UAV to SEARCH mode |
| `follow_target` | `drone_id`, `target_id` | Command FOLLOW mode |
| `paint_target` | `drone_id`, `target_id` | Command PAINT (laser lock) |
| `intercept_target` | `drone_id`, `target_id` | Command INTERCEPT |
| `cancel_track` | `drone_id` | Release from target |
| `move_drone` | `drone_id`, `target_lon`, `target_lat` | Set waypoint |
| `spike` | `lon`, `lat` | Trigger threat response at location |
| `approve_nomination` | `entry_id` | HITL Gate 1 — approve |
| `reject_nomination` | `entry_id` | HITL Gate 1 — reject |
| `authorize_coa` | `entry_id`, `coa_id` | HITL Gate 2 — authorize |
| `sitrep_query` | `query` | Request situation report |
| `retask_sensors` | `zone_id` | Retask sensors to zone |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/ws` | WebSocket — 10 Hz sim state + bidirectional commands |
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

---

## Contributing

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Write tests first: `./venv/bin/python3 -m pytest src/python/tests/`
3. Commit: `git commit -m "feat: description"`
4. Open a PR

---

## License

MIT — see [LICENSE](LICENSE) for details.
