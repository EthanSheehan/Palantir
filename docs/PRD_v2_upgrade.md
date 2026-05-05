# PRD v2: Grid-Sentinel C2 — Full System Upgrade

**Project:** Grid-Sentinel C2
**Version:** 2.0
**Date:** 2026-03-17
**Target:** Military-grade C2 demo (local deployment, single operator, desktop)

---

## 1. Executive Summary

Grid-Sentinel C2 v1 delivered a working proof-of-concept: 10Hz simulation loop, Cesium 3D visualization, dual-client WebSocket architecture, and a skeleton multi-agent kill chain. The system has a solid foundation but critical gaps prevent it from being a convincing military demo:

- **AI agents are 80% stubbed** — the kill chain doesn't actually execute
- **Frontend is a 1534-line monolith** — hard to extend with new features
- **Drones can't interact with targets** — no view, follow, or paint capabilities
- **Grid 9 layout exists but isn't integrated** with the full target simulation
- **No structured logging or proper error handling**
- **Simulation lacks fidelity** — targets detected by proximity only, no sensor model

**Primary Goal:** Take the grid 9 layout and add simulated targets that drones can **view** (camera feed), **follow** (track mode), and **paint** (laser designate/lock) — with the full F2T2EA kill chain executing via AI agents and human-in-the-loop approval.

---

## 2. Goals & Non-Goals

### Goals
- **Core:** Drones detect, view, follow, and paint simulated targets in the grid 9 UI
- Complete the F2T2EA kill chain with functional AI agents (free LLMs — Ollama/local)
- Human-in-the-loop (HITL) approval gates at Target and Engage phases
- Realistic simulation: sensor models, multiple theaters, unit type variety
- Drone video simulator shows actual tracked targets (not disconnected blocks)
- Strike Board UI for commander approve/reject/retask workflow
- Clean, maintainable codebase (modular frontend, proper error handling)
- Multi-theater support (configurable AO beyond Romania)

### Non-Goals
- Database / persistence — in-memory is fine for demo
- Auth / RBAC — single operator, no login
- Cloud deployment — local only
- Real hardware integration — all simulated
- Mobile / tablet UI — desktop only
- Multi-user / shared state — single operator
- Paid LLM APIs — free models only (Ollama, vLLM, or heuristic fallback)
- CI/CD pipeline — nice to have, not blocking

---

## 3. Architecture Overview

### 3.1 Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  Grid 9 Layout + Cesium 3D + Modular JS/TS                  │
│  ┌──────────┬──────────┬──────────┬──────────┐             │
│  │ Map View │ Strike   │ Tactical │ Drone    │             │
│  │ (Cesium) │ Board    │ HUD/Feed │ Controls │             │
│  └──────────┴──────────┴──────────┴──────────┘             │
│              WebSocket (state + video feeds)                 │
├─────────────────────────────────────────────────────────────┤
│                      API LAYER                               │
│  FastAPI                                                     │
│  ┌──────────┬──────────┬──────────┬──────────┐             │
│  │ WS       │ Sim      │ HITL     │ Config   │             │
│  │ Gateway  │ Control  │ Actions  │ API      │             │
│  └──────────┴──────────┴──────────┴──────────┘             │
├─────────────────────────────────────────────────────────────┤
│                    AGENT LAYER                               │
│  LangGraph + Free LLM (Ollama) + Heuristic Fallback         │
│  ┌──────────┬──────────┬──────────┬──────────┐             │
│  │ ISR      │ Strategy │ Tactical │ Effectors│             │
│  │ Observer │ Analyst  │ Planner  │ Agent    │             │
│  ├──────────┼──────────┼──────────┼──────────┤             │
│  │ Pattern  │ AI Task  │ Battlesp.│ Synthesis│             │
│  │ Analyzer │ Manager  │ Manager  │ Query    │             │
│  └──────────┴──────────┴──────────┴──────────┘             │
│  LLM: Ollama (llama3/mistral) → Heuristic fallback          │
├─────────────────────────────────────────────────────────────┤
│                  SIMULATION LAYER                            │
│  ┌──────────┬──────────┬──────────┬──────────┐             │
│  │ Sim      │ Sensor   │ Target   │ Drone    │             │
│  │ Engine   │ Model    │ Behavior │ Video    │             │
│  │          │ (Pd/RCS) │ (Red AI) │ Sim      │             │
│  └──────────┴──────────┴──────────┴──────────┘             │
│  ┌──────────┬──────────┐                                    │
│  │ Theater  │ Scenario │                                    │
│  │ Config   │ Manager  │                                    │
│  └──────────┴──────────┘                                    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend | Modular JS/TS on grid 9 base | Grid 9 layout is proven; split into modules |
| LLM | Ollama (local, free) + heuristic fallback | No paid APIs; works offline/air-gapped |
| Persistence | In-memory (current state only) | Demo scope; no DB overhead |
| Auth | None | Single operator demo |
| Deployment | `grid-sentinel.sh` launcher | Keep it simple; Docker optional later |
| Logging | `structlog` → JSON | Replace prints; debug-friendly |
| Video sim | Integrated with sim_engine targets | Drones see actual simulated entities |

---

## 4. Upgrade Phases

### Phase 1: Simulation Core — Drone-Target Interaction
**Goal:** Drones can detect, view, follow, and paint targets. This is the #1 priority.

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 1.1 | **Sensor model** — Replace 0.5° proximity detection with Pd(range, RCS, altitude, aspect) | P0 | L |
| 1.2 | **Drone modes: VIEW** — Drone orbits detected target, slews camera to track it | P0 | L |
| 1.3 | **Drone modes: FOLLOW** — Drone follows moving target, maintaining sensor lock | P0 | L |
| 1.4 | **Drone modes: PAINT** — Drone holds steady, laser designates target (lock indicator) | P0 | L |
| 1.5 | **Target behavior** — Expand target types (MANPADS, radar, C2 node, logistics); add shoot-and-scoot, concealment | P0 | M |
| 1.6 | **Video sim integration** — Drone camera shows actual sim_engine target entities, not random blocks | P0 | L |
| 1.7 | **Target detection events** — Publish detection/track/lock events to agent layer and frontend | P0 | M |
| 1.8 | **Multi-drone coordination** — Multiple drones can track same target, handoff tracking when one RTBs | P1 | L |

### Phase 2: Frontend — Grid 9 + Target Interaction UI
**Goal:** Grid 9 layout with full target interaction controls.

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 2.1 | **Merge grid 9 layout** as new baseline (replace current src/frontend) | P0 | M |
| 2.2 | **ENEMIES tab** — Full hostile entity list with type/status/coords, click-to-select | P0 | M |
| 2.3 | **Drone action buttons** — VIEW / FOLLOW / PAINT commands on selected drone+target pair | P0 | L |
| 2.4 | **Tactical HUD** — Live video feed from selected drone showing tracked target | P0 | L |
| 2.5 | **Target visualization** — Threat icons on map, detection rings, lock indicator animations | P0 | M |
| 2.6 | **Strike Board panel** — Nominated targets, COA options, APPROVE/REJECT/RETASK buttons | P0 | L |
| 2.7 | **Agent message feed** — Tactical Assistant showing kill chain progress and recommendations | P0 | M |
| 2.8 | **Frontend modularization** — Split monolithic app.js into <400-line modules | P1 | L |
| 2.9 | **Drone camera view** — Picture-in-picture or modal showing drone's perspective of target | P1 | M |

### Phase 3: AI Agent Completion
**Goal:** Full F2T2EA kill chain with free LLM reasoning and HITL gates.

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 3.1 | **Ollama integration** — LLM adapter for local models (llama3, mistral) with heuristic fallback | P0 | M |
| 3.2 | **ISR Observer** — Sensor fusion from multiple drones, track correlation, contact classification | P0 | L |
| 3.3 | **Strategy Analyst** — ROE evaluation, priority scoring, strike board nomination with reasoning | P0 | L |
| 3.4 | **Tactical Planner** — COA generation: which drone(s), which effector, time-to-effect, Pk estimate | P0 | L |
| 3.5 | **Effectors Agent** — Execute engagement simulation, collect BDA, report results | P0 | L |
| 3.6 | **HITL gates** — Approval required at Target nomination and Engage authorization | P0 | M |
| 3.7 | **Pattern Analyzer** — Implement anomaly detection (currently NotImplementedError) | P1 | M |
| 3.8 | **AI Tasking Manager** — Auto-retask drones to priority targets | P1 | M |
| 3.9 | **Battlespace Manager** — Threat rings, weapon engagement zones, no-fly areas | P1 | M |
| 3.10 | **Synthesis Query Agent** — Generate SITREP summaries on demand | P1 | M |
| 3.11 | **Agent reasoning traces** — Every recommendation includes "Why" chain shown in UI | P0 | S |

### Phase 4: Simulation Fidelity & Multi-Theater
**Goal:** Credible, configurable simulation across multiple theaters.

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 4.1 | **Theater config files** — YAML/JSON defining AO boundaries, terrain features, unit placements, force composition | P0 | L |
| 4.2 | **Theater: Romania** — Current default, upgraded with new target types and sensor model | P0 | M |
| 4.3 | **Theater: South China Sea** — Maritime scenario with ship-based targets, island bases | P1 | M |
| 4.4 | **Theater: Baltic** — Dense urban + forest terrain, NATO eastern flank scenario | P1 | M |
| 4.5 | **Realistic unit types** — MANPADS, early warning radar, mobile C2 node, logistics convoy, MLRS | P0 | M |
| 4.6 | **Red force AI** — Enemy units react: shoot-and-scoot after firing, camouflage when drone detected, decoys | P1 | L |
| 4.7 | **Weather layer** — Time-of-day + cloud cover affects EO/IR sensor detection probability | P2 | M |
| 4.8 | **UAV endurance** — Fuel/battery model, RTB when low, handoff tracking to relief drone | P2 | M |
| 4.9 | **Terrain masking** — Basic LOS (line-of-sight) check using elevation, targets hidden behind hills | P2 | L |

### Phase 5: Code Quality & Hardening
**Goal:** Stable, maintainable codebase ready for further development.

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 5.1 | **Structured logging** — Replace all `print()` with `structlog` | P0 | S |
| 5.2 | **Error handling** — Replace bare `except:`, add typed handlers | P0 | M |
| 5.3 | **requirements.txt** — Add missing deps (fastapi, uvicorn, numpy, opencv-python) | P0 | XS |
| 5.4 | **Secret management** — `.env.example`, remove hardcoded keys, validate at startup | P0 | S |
| 5.5 | **Input validation** — Pydantic models for all WebSocket payloads | P1 | M |
| 5.6 | **WebSocket hardening** — Fix 0.1s timeout, add backpressure, reconnect logic | P1 | S |
| 5.7 | **Unit tests to 80%+** — Focus on sim engine, agent layer, sensor model | P1 | L |
| 5.8 | **Integration tests** — Full kill chain end-to-end test | P1 | L |
| 5.9 | **GitHub Actions CI** — Lint (ruff), pytest, Playwright on push | P2 | M |

---

## 5. HITL (Human-in-the-Loop) Design

### Gate 1: Target Nomination (Strategy Analyst → Operator)
```
Strategy Analyst recommends target for strike board
  → Strike Board UI displays:
    - Target ID, type, confidence score
    - Supporting evidence (sensor tracks, drone feed snapshot)
    - ROE evaluation with reasoning trace
    - Risk assessment (collateral, blue-on-blue proximity)
  → Operator action: APPROVE | REJECT | RETASK (request more intel)
```

### Gate 2: Engagement Authorization (Tactical Planner → Operator)
```
Tactical Planner presents COA options
  → Strike Board UI displays:
    - 3 COA options ranked by speed, Pk, risk
    - Assigned drone(s) and effector type
    - Time-to-effect estimate
    - Reasoning trace for each option
  → Operator action: AUTHORIZE COA-X | REJECT | MODIFY
  → Effectors Agent executes only on AUTHORIZE
```

### Autonomous Phases (No approval needed)
- **Find** — ISR Observer detects contacts autonomously
- **Fix** — ISR Observer correlates tracks
- **Track** — AI Tasking Manager retasks drones
- **Assess** — Effectors Agent collects BDA

---

## 6. Drone Interaction Model

### Current State
- Drones have 3 modes: `idle`, `serving` (on-station in zone), `repositioning` (moving to zone)
- Detection is binary: target within 0.5° = detected
- No camera/sensor simulation tied to actual targets
- Video simulator shows random "blocks", not sim_engine entities

### Target State

```
Drone Modes (expanded):
  IDLE         — On station, scanning assigned zone
  SCANNING     — Active search pattern in zone (circular/grid)
  VIEWING      — Orbiting detected target, camera slewed to track
  FOLLOWING    — Pursuing moving target, maintaining sensor lock
  PAINTING     — Holding position, laser designating target (lock)
  REPOSITIONING — Transiting to new zone or target area
  RTB          — Returning to base (low fuel/battery)

Target States:
  UNDETECTED   — Not yet found by any sensor
  DETECTED     — Initial contact (bearing + rough position)
  TRACKED      — Continuous track maintained by ≥1 drone
  IDENTIFIED   — Type classified with confidence score
  NOMINATED    — On strike board, awaiting HITL approval
  LOCKED       — Drone painting target, ready for engagement
  ENGAGED      — Weapon released
  DESTROYED    — BDA confirms kill
  ESCAPED      — Target lost or moved out of sensor range
```

### Drone-Target Interaction Flow
```
1. Drone in SCANNING mode detects target → target becomes DETECTED
2. ISR Observer classifies → target becomes IDENTIFIED
3. Operator selects drone + target → commands VIEW
4. Drone enters VIEWING mode, orbits target, video feed shows entity
5. Strategy Analyst evaluates → nominates to strike board (NOMINATED)
6. Operator reviews strike board → APPROVES
7. Operator commands FOLLOW if target moving, or PAINT if stationary
8. Drone enters FOLLOWING/PAINTING mode → target becomes LOCKED
9. Tactical Planner generates COA → Operator AUTHORIZES
10. Effectors Agent executes → target ENGAGED → BDA → DESTROYED/ESCAPED
```

---

## 7. LLM Strategy (Free Models Only)

```python
# Provider priority (all free/local):
providers:
  - primary: ollama/llama3.3:70b     # Best reasoning (if GPU allows)
  - fast: ollama/llama3.2:8b         # High-frequency calls (ISR Observer)
  - fallback: heuristic engine        # If Ollama not running

# Agent → model mapping:
ISR Observer:       fast    (called frequently, needs speed)
Strategy Analyst:   primary (ROE reasoning needs quality)
Tactical Planner:   primary (COA generation needs quality)
Effectors Agent:    fast    (execution is mostly procedural)
Pattern Analyzer:   primary (anomaly detection needs reasoning)
Synthesis Query:    primary (SITREP generation needs quality)
```

If Ollama is not installed or running, all agents fall back to the existing heuristic engines. The system must be fully functional without any LLM.

---

## 8. Theater Configuration Format

```yaml
# theaters/romania.yaml
name: "Romania Eastern Flank"
description: "NATO defensive scenario in Romanian AO"
bounds:
  min_lon: 20.26
  max_lon: 29.67
  min_lat: 43.62
  max_lat: 48.27
grid:
  cols: 50
  rows: 50
blue_force:
  uavs:
    count: 20
    type: MQ-9
    base: [25.0, 45.5]  # Bucharest area
    endurance_hours: 24
    sensor_range_km: 40
red_force:
  units:
    - type: SAM
      count: 3
      behavior: stationary
      threat_range_km: 30
    - type: TEL
      count: 4
      behavior: shoot_and_scoot
      speed_kmh: 40
    - type: TRUCK
      count: 8
      behavior: patrol
      speed_kmh: 60
    - type: CP
      count: 2
      behavior: stationary
    - type: MANPADS
      count: 6
      behavior: ambush
      threat_range_km: 5
    - type: RADAR
      count: 2
      behavior: stationary
      detection_range_km: 100
environment:
  weather: clear  # clear | overcast | rain
  time_of_day: day  # day | night | dawn | dusk
  terrain: mixed  # flat | mountainous | urban | forest | mixed
```

---

## 9. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Drone-target interaction | None | VIEW / FOLLOW / PAINT fully functional |
| Kill chain execution | Stubbed | Full F2T2EA with HITL gates |
| Agent completion | 20% functional | 100% (with heuristic fallback) |
| Video sim | Random blocks | Shows actual tracked targets |
| Theaters | Romania only | 3 configurable theaters |
| Target types | 4 (SAM/TEL/TRUCK/CP) | 8+ with distinct behaviors |
| Detection model | Binary proximity | Probabilistic (Pd/range/RCS) |
| Frontend | 1534-line monolith | Modular <400-line files |
| Red force AI | Random walk | Reactive (shoot-and-scoot, concealment) |
| LLM cost | $0 (not running) | $0 (Ollama local) |

---

## 10. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Ollama model too slow for 10Hz loop | HIGH | HIGH | Async agent calls, never block sim tick; heuristic fallback |
| Llama3 reasoning too weak for ROE evaluation | MEDIUM | MEDIUM | Prompt engineering + heuristic validation layer |
| Grid 9 merge breaks existing E2E tests | MEDIUM | HIGH | Incremental merge, run Playwright after each step |
| Video sim integration is complex | HIGH | MEDIUM | Start with simple overlay, iterate to full integration |
| Scope creep beyond demo needs | HIGH | MEDIUM | Strict non-goals; "does it make the demo better?" filter |
| Sensor model math complexity | MEDIUM | LOW | Start simple (range-only Pd), add RCS/weather later |

---

## 11. Implementation Team (Agent Swarm)

See `docs/upgrade_swarm_plan.md` for the detailed agent team assignments and execution order.
