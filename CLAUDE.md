# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Palantir is a decision-centric AI-assisted Command & Control (C2) system that automates the F2T2EA kill chain (Find, Fix, Track, Target, Engage, Assess) using multi-agent AI orchestration, coordinated drone swarm operations with multi-sensor fusion, a physics-based tactical simulator, and a professional React+Blueprint+Cesium 3D geospatial frontend.

## Running the System

```bash
# Launch everything (backend + frontend + drone simulator)
./palantir.sh

# Launch in demo auto-pilot mode (full F2T2EA kill chain, no human input needed)
./palantir.sh --demo
./palantir.sh --demo --no-sim    # without drone video simulator

# Or run components individually:
./venv/Scripts/python src/python/api_main.py              # FastAPI backend on :8000
cd src/frontend-react && npm run dev -- --port 3000    # React dashboard on :3000 (Vite)
./venv/Scripts/python src/python/vision/video_simulator.py  # Drone simulator
DEMO_MODE=true ./venv/Scripts/python src/python/api_main.py  # Backend in demo mode
```

## Tests

```bash
# Run all tests (1811 tests across 35 test files)
./venv/Scripts/python -m pytest src/python/tests/

# Run a single test file
./venv/Scripts/python -m pytest src/python/tests/test_pattern_analyzer.py
```

## Dependencies

```bash
# Install Python dependencies into the existing venv
./venv/Scripts/pip install -r requirements.txt
```

Environment variables go in a `.env` file (loaded via python-dotenv). Required for LangChain/OpenAI agent features (e.g. `OPENAI_API_KEY`).

## Architecture

### Four Main Subsystems

**1. FastAPI Backend (`src/python/api_main.py`)**
- WebSocket server running a 10Hz simulation loop
- Dual-client model: `DASHBOARD` clients (frontend) and `SIMULATOR` clients (drone sim)
- `TacticalAssistant` embedded in the loop generates AI recommendations on new target detections
- `demo_autopilot()` async loop (when `DEMO_MODE=true`): auto-approves HITL nominations, generates COAs, auto-authorizes, simulates engagement with probabilistic outcomes
- Broadcasts full simulation state as JSON each tick (drones, targets, zones, assessment, ISR queue, enemy UAVs, swarm tasks)
- Three autonomy levels: MANUAL, SUPERVISED (AI proposes, operator approves), AUTONOMOUS
- Intel feed system with subscription-filtered event routing (INTEL, COMMAND, SENSOR feeds)

**2. Simulation Engine + Verification + Fusion + Swarm + Assessment**
- `sim_engine.py` — `SimulationModel` manages UAV positions/modes and target movement (SAM, TEL, TRUCK, CP, MANPADS, RADAR, C2_NODE, LOGISTICS, ARTILLERY, APC), plus enemy UAV simulation (RECON/ATTACK/JAMMING/EVADING)
- `verification_engine.py` — pure-function state machine advancing targets through DETECTED → CLASSIFIED → VERIFIED → NOMINATED with per-target-type thresholds and regression timeouts; DEMO_FAST preset halves times for demo mode
- `sensor_fusion.py` — complementary fusion across sensor types using `1 - ∏(1-ci)` with max-within-type deduplication; frozen `SensorContribution` and `FusionResult` dataclasses
- `sensor_model.py` — Radar range equation upgrade (Nathanson model) with Pd based on range, RCS, weather, sensor type
- `kalman_fusion.py` — Kalman filter multi-sensor fusion for track state estimation
- `jammer_model.py` — Electronic warfare jamming model for enemy countermeasures
- `swarm_coordinator.py` — greedy UAV-to-target assignment with sensor-gap detection, priority scoring, 120s task expiry, idle-count guard, auto-release on target state transitions
- `battlespace_assessment.py` — pure-function threat clustering, coverage gap identification, zone threat scoring, and movement corridor detection
- `isr_priority.py` — ISR priority queue builder ranking targets by urgency (threat weight × verification gap × sensor coverage)
- `intel_feed.py` — subscription-filtered event broadcast router (INTEL_FEED, COMMAND_FEED, SENSOR_FEED)
- UAV modes: IDLE, SEARCH, FOLLOW, PAINT, INTERCEPT, SUPPORT, VERIFY, OVERWATCH, BDA, REPOSITIONING, RTB
- Fixed-wing physics: `_turn_toward()` for smooth heading changes, `MAX_TURN_RATE` circular loiter in SEARCH, all tracking modes use gradual arcs
- Mode commands from frontend: SEARCH (releases target), FOLLOW/PAINT/INTERCEPT (requires target selection)
- Theater-configurable via YAML files in `theaters/` (Romania, South China Sea, Baltic)
- Zone-based imbalance tracking drives UAV repositioning logic

**3. React Frontend (`src/frontend-react/`)**
- React + Vite + TypeScript with Blueprint dark theme and Zustand state
- Served by Vite dev server on `:3000` (`npm run dev -- --port 3000`)
- 4 sidebar tabs: MISSION / ASSETS / ENEMIES / ASSESS
- MISSION tab: Theater selector, Tactical AIP Assistant, Intel Feed, Command Log, ISR Queue, Strike Board, Grid Controls, Autonomy Toggle, Coverage Mode Toggle
- ASSETS tab: Drone cards with mode buttons, autonomy overrides, transition approval toasts
- ENEMIES tab: Target cards with VerificationStepper, FusionBar, SensorBadge, SwarmPanel; EnemyUAV cards
- ASSESS tab: ThreatClusterCard, CoverageGapAlert, ZoneThreatHeatmap
- 6 map modes (OPERATIONAL, COVERAGE, THREAT, FUSION, SWARM, TERRAIN) with keyboard shortcuts 1-6
- 5 Cesium layer overlays: coverage, threat, fusion, swarm, terrain (`cesium/layers/`)
- Multi-layout drone camera PIP (SINGLE/PIP/SPLIT/QUAD) with 4 sensor modes (EO/IR, SAR, SIGINT, FUSION)
- SensorHUD, SigintDisplay (RF spectrum waterfall), CameraPresets (OVERVIEW/TOP DOWN/OBLIQUE/FREE)
- Cesium globe with all entity hooks: drones, targets, zones, flow lines, compass, range rings, lock indicators, assessment overlays, enemy UAVs, swarm lines
- Custom event bridge (`palantir:send`, `palantir:placeWaypoint`, `palantir:openDetailMap`) for Cesium→React WebSocket communication
- LayerPanel for per-layer visibility toggles, MapModeBar for mode switching
- Legacy vanilla JS frontend remains in `src/frontend/` for reference

**4. AI Agent Layer (`src/python/agents/`)**

Nine LangGraph/LangChain agents — four in the kill chain pipeline plus five support agents:
- `isr_observer.py` — sensor fusion (UAV, satellite, SIGINT)
- `strategy_analyst.py` — ROE evaluation and priority scoring
- `tactical_planner.py` — Course of Action (COA) generation
- `effectors_agent.py` — execution and Battle Damage Assessment
- `pattern_analyzer.py` — activity pattern analysis across targets
- `ai_tasking_manager.py` — sensor retasking optimization
- `battlespace_manager.py` — map layers + threat ring management
- `synthesis_query_agent.py` — SITREP generation and NL queries
- `performance_auditor.py` — system performance monitoring

Agents communicate through Pydantic models defined in `src/python/core/ontology.py`. This is the shared data contract — all detection, identity, and tasking types live here.

### State Management

- LangGraph state with annotated reducers lives in `src/python/core/state.py`
- The `add` reducer pattern is used for accumulating strike board entries, tasking requests, and rejected actions
- `src/python/schemas/ontology.json` provides JSON serialization of the ontology
- Frontend state: Zustand store (`SimulationStore.ts`) with typed payloads for all simulation data

### WebSocket Protocol

The backend sends JSON payloads each tick containing drone positions, target positions, grid zone states, theater bounds, assessment data, ISR queue, enemy UAVs, swarm tasks, and tactical assistant messages. The frontend subscribes and updates Cesium entities in real time. Simulator clients send back video frames (base64 MJPEG) and telemetry.

Key WebSocket actions: `scan_area`, `follow_target`, `paint_target`, `intercept_target`, `intercept_enemy`, `cancel_track`, `move_drone`, `spike`, `approve_nomination`, `reject_nomination`, `retask_nomination`, `authorize_coa`, `reject_coa`, `verify_target`, `retask_sensors`, `set_autonomy_level`, `set_drone_autonomy`, `approve_transition`, `reject_transition`, `request_swarm`, `release_swarm`, `set_coverage_mode`, `set_roe`, `load_scenario`, `save_checkpoint`, `load_checkpoint`, `set_speed`, `pause`, `resume`, `step`, `set_weather`, `get_report`, `subscribe`, `subscribe_sensor_feed`, `reset`, `SET_SCENARIO`.

### Key Python Modules (non-agent)

| Module | Purpose |
|--------|---------|
| `sim_engine.py` | Physics simulation, UAV/target/enemy UAV management |
| `verification_engine.py` | Target verification state machine |
| `sensor_fusion.py` | Multi-sensor complementary fusion |
| `sensor_model.py` | Probabilistic detection model (Pd, RCS, weather) |
| `swarm_coordinator.py` | Multi-UAV task assignment with sensor-gap detection |
| `battlespace_assessment.py` | Threat clustering, coverage gaps, zone scoring |
| `isr_priority.py` | ISR priority queue builder |
| `intel_feed.py` | Subscription-filtered event broadcast |
| `pipeline.py` | F2T2EA kill chain orchestrator |
| `hitl_manager.py` | Two-gate HITL approval system |
| `theater_loader.py` | YAML theater configuration loader |
| `llm_adapter.py` | Multi-provider LLM fallback (Gemini → Anthropic → heuristic) |
| `event_logger.py` | Async JSONL event logging with daily rotation |
| `config.py` | Pydantic-settings env var management |
| `roe_engine.py` | Rules of Engagement engine with YAML config |
| `audit_trail.py` | Tamper-evident audit logging of all decisions |
| `hungarian_swarm.py` | Hungarian algorithm optimal UAV-target assignment |
| `persistence.py` | SQLite state persistence for mission restart |
| `auth.py` | WebSocket JWT authentication and token validation |
| `explainability.py` | AI decision explainability engine for recommendations |
| `autonomy_matrix.py` | Dynamic autonomy level management (MANUAL/SUPERVISED/AUTONOMOUS) |
| `confidence_gate.py` | Confidence-based decision gating for safety |
| `override_capture.py` | Human override recording and analysis |
| `aar_engine.py` | After Action Review engine for post-mission analysis |
| `kill_chain_tracker.py` | F2T2EA kill chain state tracker (Find→Fix→Track→Target→Engage→Assess) |
| `sim_controller.py` | Simulation pause/resume/speed control |
| `weather_engine.py` | Weather effects on sensor performance (rain, fog, wind) |
| `uav_logistics.py` | Fuel/ammo/maintenance tracking and constraints |
| `terrain_model.py` | Terrain elevation and line-of-sight computation |
| `rbac.py` | Role-based access control with JWT authentication |
| `llm_sanitizer.py` | LLM prompt injection defense |
| `report_generator.py` | JSON/CSV report generation |
| `checkpoint.py` | Mission checkpoint/restore functionality |
| `scenario_engine.py` | YAML scenario scripting engine |
| `forward_sim.py` | Clone sim + project forward for COA evaluation |
| `delta_compression.py` | WebSocket delta encoding for bandwidth reduction |
| `vectorized_detection.py` | NumPy vectorized detection loop (10-50x speedup) |
| `comms_sim.py` | Communication degradation simulation (FULL/CONTESTED/DENIED) |
| `cep_model.py` | CEP-based engagement outcomes (Rayleigh miss-distance model) |
| `dbscan_clustering.py` | DBSCAN clustering with persistent IDs |
| `sensor_weighting.py` | Dynamic per-sensor fitness based on weather/time/target |
| `lost_link.py` | Per-drone lost-link behavior (LOITER/RTB/SAFE_LAND/CONTINUE) |
| `uav_kinematics.py` | 3-DOF point-mass with wind, collision avoidance, PN guidance |
| `corridor_detection.py` | Douglas-Peucker path simplification + heading consistency |

## Integrated Agent Workflow (MANDATORY)

This project uses four complementary systems that work together:

| System | Role | Invocation |
|--------|------|------------|
| **everything-claude-code** | Code quality agents (review, TDD, security, build) | `subagent_type: "everything-claude-code:<agent>"` |
| **GSD (Get Shit Done)** | Spec-driven planning, phased execution, context rot prevention | `/gsd:*` slash commands |
| **DevFleet** | Parallel execution in isolated git worktrees with mission DAG | `/everything-claude-code:devfleet` |
| **Ralph** | Autonomous loop execution for unattended task completion | `ralph` CLI from terminal |

### CORE RULE: Always Spawn Agent Teams

Never work alone. For every non-trivial task, spin up a team of subagents in parallel. Use the right model for each agent (haiku for lightweight, sonnet for coding, opus for architecture). See `~/.claude/rules/agents.md` for full team composition rules.

### When to Use Which System

- **Interactive single tasks** (bug fix, small feature, 1-3 files): ECC agents directly
- **Parallelizable feature** (independent parts, 4-10 files): DevFleet worktrees + ECC review
- **Multi-phase feature** (new subsystem, 10+ files): GSD phases → DevFleet execution → ECC review
- **Unattended batch work** (task list, PRD, 20+ tasks): Ralph loop (can spawn DevFleet per iteration)
- **Ad-hoc tasks with GSD guarantees**: `/gsd:quick` for atomic commits and state tracking

### everything-claude-code Agents (Proactive)

These MUST be used proactively — do not wait for the user to ask.

| Trigger | Agent (`subagent_type`) | When |
|---------|------------------------|------|
| Feature request or complex task | `everything-claude-code:planner` | Before writing any code |
| Architectural decision | `everything-claude-code:architect` | System design, scalability questions |
| New feature or bug fix | `everything-claude-code:tdd-guide` | Write tests first (RED/GREEN/IMPROVE) |
| Code written or modified | `everything-claude-code:python-reviewer` | Immediately after any Python change |
| Code written or modified | `everything-claude-code:code-reviewer` | Immediately after any non-Python change |
| Build/test failure | `everything-claude-code:build-error-resolver` | When pytest or any build fails |
| Before commit | `everything-claude-code:security-reviewer` | Check for secrets, injection, OWASP Top 10 |
| Dead code / cleanup | `everything-claude-code:refactor-cleaner` | Code maintenance tasks |
| Documentation needed | `everything-claude-code:doc-updater` | After significant changes |
| E2E testing needed | `everything-claude-code:e2e-runner` | Critical user flow validation |
| Database changes | `everything-claude-code:database-reviewer` | Schema/query changes |

### GSD Commands (User-Initiated)

Key commands for phased development:

| Command | Purpose |
|---------|---------|
| `/gsd:new-project` | Initialize project with requirements + roadmap |
| `/gsd:plan-phase N` | Research + plan phase N with fresh context |
| `/gsd:execute-phase N` | Execute all plans in parallel waves |
| `/gsd:verify-work N` | User acceptance testing |
| `/gsd:quick` | Ad-hoc task with GSD guarantees |
| `/gsd:progress` | Show current progress |
| `/gsd:debug` | Diagnose issues |
| `/gsd:map-codebase` | Analyze existing codebase |
| `/gsd:health` | System health check |

GSD stores state in `.planning/` directory (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md).

### DevFleet (Parallel Worktree Execution)

DevFleet runs parallel agents in isolated git worktrees with a mission DAG. Use `/everything-claude-code:devfleet` or let `/build` auto-select it.

Best for: parallelizable features where parts touch different files and can be implemented independently, then auto-merged.

### Ralph (Autonomous Loop)

Ralph runs Claude CLI in a loop for unattended work. Config lives in `.ralph/`.

```bash
ralph --monitor          # Start autonomous loop with dashboard
ralph-import prd.md      # Import tasks from a PRD
```

Edit `.ralph/fix_plan.md` to define the task list. Ralph handles session continuity, rate limiting, and stagnation detection automatically.

### Auto-Commit at Milestones (MANDATORY)

Commit frequently — after every logical unit of work completes. Do NOT batch changes.

**Commit after each:** test passes, feature implemented, bug fixed, refactor done, config applied. If you haven't committed in 2-3 tool calls after making changes, you're overdue. Use conventional commits (`feat:`, `fix:`, `test:`, `docs:`, etc.).

### Auto Documentation & README Updates (MANDATORY)

Every commit that changes behavior MUST include docs updates in the same commit:
- New feature/endpoint → update `README.md` + `CLAUDE.md`
- New file/module → update `CLAUDE.md` architecture section
- Config/env/CLI changes → update `README.md` setup section
- Architecture decisions → update `CLAUDE.md` + `docs/INTEGRATED_WORKFLOW.md`

Spawn `everything-claude-code:doc-updater` (haiku, background) for large doc work. Do small README/CLAUDE.md updates inline.

### Parallel Execution (REQUIRED)

Always launch independent agents in parallel. Example: after writing a feature, launch `python-reviewer` and `security-reviewer` simultaneously — never sequentially.

### Development Pipelines

**ECC only — single task (1-3 files):**
1. **Plan** → `everything-claude-code:planner` (sonnet)
2. **TDD** → `everything-claude-code:tdd-guide` (sonnet)
3. **Implement** → write code
4. **Commit** → auto-commit milestone (test green)
5. **Review** → `python-reviewer` + `security-reviewer` (parallel, sonnet)
6. **Fix** → address findings
7. **Commit + Docs** → commit fixes + update README/CLAUDE.md

**DevFleet — parallelizable feature (4-10 files):**
1. **Plan** → `everything-claude-code:planner` (sonnet) → break into independent units
2. **Execute** → DevFleet dispatches each unit to isolated worktree (sonnet per mission)
3. **Auto-merge** → worktrees merge on completion
4. **Commit** → auto-commit merged work
5. **Review** → `python-reviewer` + `security-reviewer` (parallel, sonnet)
6. **Fix + Commit + Docs** → commit fixes + update README/CLAUDE.md

**GSD + DevFleet — major feature (10+ files):**
1. `/gsd:discuss-phase N` → capture decisions
2. `/gsd:plan-phase N` → research + plan (opus for planning, fresh context)
3. **DevFleet** executes plans as parallel worktree missions (sonnet)
4. **Commit** → auto-commit after each phase/wave
5. `/gsd:verify-work N` → user acceptance testing
6. **Review** → `python-reviewer` + `security-reviewer` (parallel, sonnet)
7. **Commit + Docs** → commit fixes + update README/CLAUDE.md/INTEGRATED_WORKFLOW.md

**Ralph — unattended batch (20+ tasks):**
1. Edit `.ralph/fix_plan.md` with tasks
2. `ralph --monitor` → autonomous execution with safety guardrails
3. Auto-commits after each task completion
4. Review results when complete
