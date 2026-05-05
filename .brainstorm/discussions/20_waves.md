# 20 — Dependency & Wave Map

**Author:** Dependency & Wave Mapper
**Date:** 2026-03-20
**Source documents:** 01_archaeology through 15_best_practices

---

## Dependency Graph Summary

Before the waves, the critical dependency chains:

```
FOUNDATION (no dependencies)
  ├── Bug fixes (01-A,B,C,D)
  ├── DevEx tooling (09: CI, lint, pre-commit)
  ├── Security baseline (08: auth, input validation, message size)
  ├── Performance quick-wins (07: get_state cache, dict lookups, ISR thread)
  └── Test infrastructure (06-P0: autopilot tests, payload tests, Hypothesis, Locust)

ARCHITECTURE REFACTOR (depends on: bug fixes + tests)
  ├── sim_engine.py split → UAVPhysicsEngine, TargetBehaviorEngine, DetectionPipeline
  ├── api_main.py split → handlers, loop, autopilot, assistant
  └── handle_payload() dispatch → command registry

ROE ENGINE (depends on: architecture refactor)
  └── Deterministic ROE rules replace non-deterministic strategy_analyst

AUTONOMOUS OPERATIONS CORE (depends on: ROE engine + architecture refactor)
  ├── Autopilot refactor (fix SCANNING bug, sequential sleep bug, untestable design)
  ├── Autonomy model upgrade (per-action matrix, time-bounded grants)
  ├── Audit trail (structured log per autonomous action)
  └── Confidence-gated authority (escalate low-confidence to operator)

PERSISTENCE LAYER (depends on: architecture refactor)
  └── SQLite/Postgres → enables AAR, scenario restore, mission audit

SENSOR FUSION UPGRADE (depends on: architecture refactor + Shapely/FilterPy)
  └── Kalman tracks in sensor_fusion.py

SWARM COORDINATOR UPGRADE (depends on: architecture refactor)
  └── Hungarian/auction algorithm, autonomy-level awareness

UI / XAI (depends on: autonomous operations core)
  ├── Reasoning panel (XAI "why did it do that?")
  ├── Pre-autonomy briefing screen
  ├── Global alert center / strike board overlay
  └── Autonomy grant UI with countdown timers

ADVANCED MODULES (depends on: persistence + core upgrade)
  ├── After-Action Review engine (needs persistence)
  ├── Scenario scripting (needs persistence + sim controls)
  ├── Weather/EW engine (needs architecture split)
  └── Logistics module (needs sim split + persistence)

INTEROPERABILITY (depends on: architecture + security)
  └── CoT/TAK bridge, MIL-STD-2525 symbology

RL / ADVANCED AI (depends on: everything above)
  └── PettingZoo wrapper, policy training, behavioral cloning
```

---

## Wave 1 — Foundation (All Independent, Maximum Parallelism)

**No prerequisites. All items can be executed simultaneously by separate agents.**

### 1A: Critical Bug Fixes (01 — Archaeology)
- Fix `"SCANNING"` → `"SEARCH"` in `_find_nearest_available_uav()` (api_main.py:275)
- Fix dead-branch enemy cleanup: `enemy_intercept_dispatched` set grows unbounded (api_main.py:323)
- Fix blocking `input()` in `pipeline.py:81` — replace with async-compatible stub
- Fix `TacticalAssistant._nominated` set: never pruned — cap or TTL
- Fix `_prev_target_states` dict: never pruned
- Fix silent `except ValueError: pass` in autopilot COA authorization (api_main.py:426)
- Implement `_generate_response()` in battlespace_manager, pattern_analyzer, synthesis_query_agent (three NotImplementedError stubs)

**Effort:** ~1 day | **Unlock:** autopilot actually dispatches SEARCH-mode drones; agents no longer crash

### 1B: DevEx Tooling (09 — DevEx)
- Add `pyproject.toml` with ruff, mypy, pytest config, 80% coverage threshold
- Add `.pre-commit-config.yaml` (ruff, black, mypy, eslint)
- Add `.github/workflows/test.yml` (pytest + coverage + ruff on every PR)
- Add `Makefile` with setup/run/test/lint targets
- Add `/health` endpoint to api_main.py
- Add `.editorconfig`

**Effort:** ~1 day | **Unlock:** all subsequent development has quality gates; CI catches regressions automatically

### 1C: Security Baseline (08 — Security)
- Add WebSocket message size guard before `json.loads()`
- Fix HITL replay: check `old.status == "PENDING"` before allowing transition
- Add allowlist validation for `theater_name` against `list_theaters()`
- Add range validation: lat (-90,90), lon (-180,180), confidence (0,1)
- Add input allowlist for `set_coverage_mode`
- Add `subscribe` / `subscribe_sensor_feed` element type validation
- Add SITREP query length limit
- Add demo autopilot circuit breaker: max N auto-approvals, halt if no DASHBOARD client

**Effort:** ~1 day | **Unlock:** system is no longer trivially exploitable; safe to demo externally

### 1D: Performance Quick-Wins (07 — Performance)
- Cache `get_state()` once per tick (eliminate 2-3 redundant O(U×T) calls)
- Replace `_find_uav/target/enemy_uav` O(N) linear scans with dict lookups
- Move `build_isr_queue()` into the `asyncio.to_thread()` assessment call
- Fix event_logger: keep file handle open, flush periodically instead of reopen every write
- Add `detection_range_km` early-exit to detection loop

**Effort:** ~0.5 day | **Unlock:** 10-50% tick speedup at current scale; maintains 10Hz at larger entity counts

### 1E: Test Infrastructure P0 (06 — Testing)
- Add `Hypothesis` property-based tests to sensor_fusion, verification_engine, swarm_coordinator
- Add `Locust` WebSocket load test: 50 concurrent DASHBOARD clients at 10Hz
- Add `pytest-benchmark` for tick() and assessment() hot paths
- Add tests for all `handle_payload()` action handlers (currently ~2/20 covered)
- Add tests for `tactical_planner.py` COA generation (442 lines, zero tests)
- Add golden snapshot test for `get_state()` schema

**Effort:** ~2 days | **Unlock:** safe to refactor; regressions caught immediately

### 1F: Quick Library Additions (13 — Libraries)
- `pip install shapely` — drop into battlespace_assessment.py for polygon math
- `npm install @turf/turf` — replace ~200 lines of inline trig in Cesium hooks
- `pip install hypothesis` — already covered in 1E
- `pip install filterpy` — prototype UKF in new test file before committing to refactor
- `pip install scipy` — KD-tree for O(log n) clustering, SIGINT signal processing

**Effort:** ~0.5 day | **Unlock:** backend/frontend geometry is correct; sensor clustering faster

---

**Wave 1 Total Estimated Effort:** 5–6 person-days running in parallel (1–2 days wall-clock with team)

**What Wave 1 Enables:**
- Architecture refactor is safe (tests catch regressions)
- CI enforces quality going forward
- Autopilot dispatches correctly (SCANNING bug fixed)
- Security baseline met for external demos
- Library improvements available for Wave 2 refactors

---

## Wave 2 — Architecture Refactor (Depends on Wave 1)

**Requires:** 1A (bug fixes), 1B (DevEx), 1E (tests catching regressions)

### 2A: Split sim_engine.py God Module (03 — Architecture)
Extract from `SimulationModel` (~1,553 lines):
- `UAVPhysicsEngine` — 11 UAV modes, turn rate, orbit tracking, RTB logic (implement real RTB destination)
- `TargetBehaviorEngine` — 5 target archetypes, emit toggle, shoot-and-scoot
- `EnemyUAVEngine` — 4 enemy UAV modes, intercept confidence, intercept dispatch
- `DetectionPipeline` — sensor detection O(U×T×S), FOV computation
- `AutonomyController` — AUTONOMOUS_TRANSITIONS table, mode promotion logic
- `SimulationOrchestrator` — thin coordinator calling each engine per tick

Fix inside this refactor:
- RTB mode: implement real RTB destination rather than "drift slowly for now"
- `altitude_penalty` in sensor_model.py: apply the documented but unused variable
- Remove stale VIEWING mode comment
- Fix `"SCANNING"` mode in video_simulator.py (use `"SEARCH"`)

**Effort:** ~3 days | **Unlock:** each engine testable independently; Wave 3 autonomy upgrades target AutonomyController cleanly

### 2B: Split api_main.py God File (03 — Architecture)
Extract from `api_main.py` (~1,113 lines):
- `websocket_handlers.py` — command registry replacing 200-line if/elif (plugin-style dispatch)
- `simulation_loop.py` — 10Hz loop, assessment scheduling, ISR queue dispatch
- `autopilot.py` — `demo_autopilot()` decoupled from WebSocket globals; accepts injected `sim`, `hitl`, `broadcast_fn` for testability
- `tactical_assistant.py` — `TacticalAssistant` class promoted to own module; fix `_nominated` mutation side effect
- Fix asyncio data race: `asyncio.to_thread()` reads `sim` state while main loop mutates — add a lock or snapshot-before-thread pattern

Fix inside this refactor:
- CORS origins: move hardcoded `localhost:3000` to `Grid-SentinelSettings`
- Demo autopilot delays: move local constants to `Grid-SentinelSettings`
- `_process_new_detection()`: use `logger.exception()` not `str(exc)`
- `broadcast()`: log client ID on removal

**Effort:** ~3 days | **Unlock:** autopilot is now testable; handler registration is extensible; asyncio data race eliminated

### 2C: Add autopilot Tests (06 — Testing, depends on 2B)
Now that `autopilot.py` is decoupled, add all P0 autopilot tests from 06:
- `test_demo_autopilot_approves_pending_after_delay`
- `test_demo_autopilot_dispatches_nearest_uav` (verifies SEARCH fix from 1A)
- `test_demo_autopilot_escalates_follow_to_paint`
- `test_demo_autopilot_generates_coas_after_paint`
- `test_demo_autopilot_authorizes_best_coa`
- `test_demo_autopilot_auto_intercepts_enemy_above_threshold`
- `test_demo_autopilot_skips_already_inflight`
- `test_full_kill_chain_auto_mode_completes` — UNDETECTED → AUTHORIZED integration test
- `test_supervised_requires_approval`
- `test_autonomous_fleet_with_manual_override`

**Effort:** ~1 day | **Unlock:** autopilot behavior is locked down; regressions caught in CI

### 2D: Docker Compose (13 — Libraries, 09 — DevEx)
- `Dockerfile` for FastAPI backend (Python 3.12 slim)
- `Dockerfile` for React/Vite frontend (node:20 + nginx)
- `docker-compose.yml` — backend + frontend + video_simulator; optional Redis sidecar
- Update `.github/workflows/` to build and smoke-test containers

**Effort:** ~1 day | **Unlock:** reproducible deployment on any host; CI validates container build; Redis available for Wave 3

---

**Wave 2 Total Estimated Effort:** ~8 person-days (can parallelize 2A + 2B + 2D; 2C must follow 2B)

**What Wave 2 Enables:**
- ROE Engine can target clean AutonomyController (Wave 3A)
- Persistence layer can target clean SimulationOrchestrator state (Wave 3B)
- Sensor fusion upgrade targets isolated DetectionPipeline (Wave 3C)
- Autopilot is testable and behavior-locked (Wave 3 autonomy upgrades are safe)
- Docker enables staging environment for security testing

---

## Wave 3 — Autonomous Operations Core + Persistence (Depends on Wave 2)

**Requires:** 2A, 2B, 2C, 2D

### 3A: ROE Engine (10 — Missing Modules, 15 — Best Practices)
New module: `src/python/roe_engine.py`
- `ROERule` dataclass: target_type + zone + autonomy_level + collateral → permitted/denied/escalate
- `ROEEngine.evaluate(target, autonomy_level) → ROEDecision`
- `ROEChangeLog` — immutable append-only log of rule changes
- Wire into `AutonomyController` (from 2A): ROE engine has veto power in AUTONOMOUS mode
- Wire into `strategy_analyst.py`: replaces non-deterministic LLM ROE evaluation for safety-critical path; LLM becomes advisory only
- YAML-configurable ROE rules per theater (add `roe_rules` section to theater YAML)
- 30+ unit tests: all rule combinations, escalation paths, veto behavior

**Effort:** ~2 days | **Unlock:** autonomous mode is rule-bounded, not LLM-dependent; procurement-compliant; enables confidence-gated authority in 3D

### 3B: Persistence Layer (10 — Missing Modules, 05 — Dependencies)
New module: `src/python/persistence/`
- `MissionStore` — SQLite (local) / PostgreSQL (multi-user); Pydantic model serialization
- Store on every target state transition (immutable event records)
- `StrikeArchive` — engagement outcomes with full reasoning trace
- `EventIndex` — searchable index over JSONL events (or migrate event_logger to DB)
- WebSocket actions: `save_checkpoint`, `load_mission`, `list_missions`
- REST endpoints: `GET /api/missions`, `GET /api/missions/{id}`, `POST /api/missions/{id}/restore`
- Add `pip install sqlalchemy alembic` to requirements

**Effort:** ~3 days | **Unlock:** AAR engine (Wave 4A), scenario restore (Wave 4B), structured audit trail (required for 3E)

### 3C: Sensor Fusion Upgrade — Kalman Tracks (13 — Libraries, 02 — Algorithms)
In `sensor_fusion.py`:
- Add `FilterPy` UKF per-target track state (position estimate + covariance)
- `FusionResult` gains `position_estimate: tuple[float,float]`, `position_covariance: float`
- Temporal decay for contributions not recently updated
- Cross-sensor disagreement detection (flag when EO and SAR disagree beyond threshold)
- Update 13 existing sensor_fusion tests; add 15 new Kalman-specific tests
- Companion: add `Stone Soup` evaluation in a parallel branch (decide if full migration is warranted)

**Effort:** ~2 days | **Unlock:** targets have position uncertainty bounds; ISR priority can weight by uncertainty; verification confidence is grounded

### 3D: Swarm Coordinator Upgrade (02 — Algorithms, 03 — Architecture)
In `swarm_coordinator.py`:
- Replace greedy assignment with Hungarian algorithm (scipy.optimize.linear_sum_assignment) for optimal UAV-to-target matching
- Wire autonomy level: coordinator checks `AutonomyController` before auto-assigning in SUPERVISED mode
- Add Byzantine position anomaly detection: flag UAVs reporting positions inconsistent with last known velocity
- Add automatic role promotion: if assigned drone for target is lost/RTB, promote next-best without human intervention
- Update 13 existing swarm tests; add 10 new tests for Hungarian, anomaly detection, promotion

**Effort:** ~2 days | **Unlock:** optimal sensor gap coverage; swarm is resilient to drone failures; autonomy-level-aware

### 3E: Structured Audit Trail (14 — User Needs, 15 — Best Practices)
In `event_logger.py` / new `audit_log.py`:
- Every autonomous action logs: timestamp, action_type, autonomy_level_at_time, triggering_sensor_evidence (with confidence scores), hitl_status (approved/rejected/timeout/autonomous), operator_identity (if approved)
- Every operator override logs: reason_code (WRONG_TARGET / WRONG_TIMING / ROE_VIOLATION)
- Read-only REST endpoint: `GET /api/audit` with filter by time, action_type, autonomy_level
- Tamper-evident: append-only log with SHA-256 hash chain per entry
- Wire override reason codes into `TacticalAssistant` prompt context (within-session learning)

**Effort:** ~1.5 days | **Unlock:** DoD 3000.09 compliance; procurement deliverable; operator override feedback loop; XAI accountability

---

**Wave 3 Total Estimated Effort:** ~10 person-days (3A + 3C + 3D + 3E can run in parallel; 3B sequential due to DB schema design)

**What Wave 3 Enables:**
- Confidence-gated authority (Wave 4C) has ROE engine + audit trail as prerequisites
- AAR engine has persistence as prerequisite
- XAI UI has structured reasoning to display
- Logistics module has sim architecture to integrate into

---

## Wave 4 — UX, XAI, and Autonomy Model Upgrade (Depends on Wave 3)

**Requires:** 3A (ROE), 3B (persistence), 3E (audit trail), Wave 2 architecture

### 4A: XAI Reasoning Panel ("Why Did It Do That?") (14 — User Needs, 12 — Research)
- `TacticalAssistant` upgraded to chain-of-thought prompting: model explains reasoning before concluding
- Every recommendation carries structured rationale: action, top-3 evidence factors with confidence scores, ROE rule satisfied, alternatives considered
- Frontend: "Why?" expandable panel on every HITL entry (StrikeBoardEntry, nomination toast)
- Frontend: label every AI output with its source: [AI: Gemini-2.0] / [AI: Anthropic] / [Heuristic: Rule N]
- Counterfactual threshold displayed: "If confidence drops below 0.75, autopilot will defer"
- Autopilot Decision Log panel in ASSESS tab with expandable XAI summaries

**Effort:** ~2 days | **Unlock:** operator trust calibration; DoD 3000.09 "why-did-you-do-that" compliance; procurement differentiator

### 4B: Autonomy Model Upgrade — Per-Action Matrix + Time-Bounded Grants (14 — User Needs, 15 — Best Practices)
- Extend autonomy model from [MANUAL/SUPERVISED/AUTONOMOUS] to per-action policy object:
  - Each action type (FOLLOW, PAINT, INTERCEPT, AUTHORIZE_COA, ENGAGE) has independent autonomy level
  - `set_autonomy_level` WebSocket action gains: `action_type` (optional, defaults to global), `duration_seconds` (auto-reverts), `exception_conditions` (list of target types that trigger pause-and-ask)
- Frontend: autonomy grant UI in ASSETS tab with countdown timers per active grant
- Frontend: pre-autonomy briefing screen when activating AUTONOMOUS: what will run autonomously, what requires approval, what triggers auto-reversion, active ROE rules — require explicit acknowledgment
- Confirmation dialog before AUTONOMOUS — no more one-mis-click removal of human from lethal loop
- Escape key → force MANUAL (hardware-brakeable override)
- Autonomy level preserved across theater switches (fix: currently reset on SimulationModel recreation)

**Effort:** ~2.5 days | **Unlock:** DoD disciplined autonomy compliance; time-bounded grants for research ablation studies; operator trust via predictability

### 4C: Confidence-Gated Dynamic Authority (12 — Research, 15 — Best Practices)
- In `AutonomyController`: even in AUTONOMOUS mode, escalate to operator when:
  - AI confidence < configurable threshold (default 0.80)
  - Target type is in high-value/collateral-sensitive category
  - Situation is novel (no historical analogs in session)
  - Override rate for this session exceeds 30% (operator is actively disagreeing with AI)
- "Vigilance prompts" in SUPERVISED/AUTONOMOUS modes: periodic UI acknowledgment required to confirm operator is monitoring (prevent automation complacency)
- Frontend: confidence-gated actions glow amber in the strike board (vs. green for high-confidence auto-approve)
- Calibrated confidence scores emitted with every TacticalAssistant recommendation; displayed prominently

**Effort:** ~1.5 days | **Unlock:** aligns with ACE hierarchical autonomy model; reduces inadvertent escalation; builds operator appropriate trust

### 4D: Global Alert Center + UX Critical Fixes (04 — UX)
- Global alert center overlay (not tab-local): critical events surface across all tabs
  - TransitionToast visible from all tabs (not just ASSETS) — prevents missed 10-second windows
  - New high-priority target notification with audio alert option
  - Low fuel / RTB alert system-wide
- Strike board promoted to floating overlay: PENDING nominations always visible, not buried in scroll
- ISR Queue: add one-click dispatch button (shows recommended UAVs with action buttons)
- Coverage gap → "Send Drone" dispatch action in ASSESS tab
- Keyboard shortcuts: A/R to approve/reject focused nomination, Space pause/resume, Escape MANUAL/deselect, W waypoint mode
- Implement dead buttons: Range, Detail have real actions
- Theater switch confirmation on live mission
- WebSocket reconnection: show retry count, last-connected timestamp, explain disconnection reason

**Effort:** ~2 days | **Unlock:** critical UX safety issues resolved; operators don't miss approval windows; system is demo-ready for procurement

### 4E: After-Action Review Engine (10 — Missing Modules)
New module: `src/python/aar_engine.py` + frontend AAR tab
- Variable-speed replay (1x-50x) using persisted mission snapshots (requires 3B)
- Decision timeline: AI recommendation vs. operator decision vs. outcome, plotted per target
- AI vs. operator comparison: where autopilot would have acted differently than human did
- Structured AAR report: kill chain latency per target, sensor fusion accuracy, override rate, COA selection accuracy
- Frontend: new REPLAY tab with timeline scrubber, speed selector, pause/play
- Export: mission report JSON/CSV; kepler.gl compatible event log export

**Effort:** ~3 days | **Unlock:** primary feedback loop for tuning autonomous thresholds; research reproducibility; mission debrief capability

---

**Wave 4 Total Estimated Effort:** ~11 person-days (4A + 4B + 4C + 4D can run in parallel; 4E sequential after 3B)

**What Wave 4 Enables:**
- System is procurement-demonstrable with XAI, audit trail, per-action autonomy, and pre-autonomy briefing
- Research community can use Grid-Sentinel as a testbed (reproducible scenarios, metrics export)
- Scenario scripting (Wave 5A) has simulation fidelity controls to build on
- Advanced sensor fusion (Wave 5) has per-action autonomy model to integrate with

---

## Wave 5 — Advanced Modules (Depends on Wave 3 + 4)

**Requires:** Architecture refactor (W2), persistence (3B), autonomy upgrade (4B)

### 5A: Scenario Scripting + Simulation Fidelity Controls (10 — Missing Modules)
- `ScenarioLoader` — YAML exercise scripts: inject events at T+N, spawn targets, trigger weather, simulate comms degradation
- `ScenarioPlayer` — plays scripts against live sim, emits events to `intel_feed`
- `SimController` — time compression (1x-50x), pause/resume, event injection mid-sim
- WebSocket action: `sim_control` (speed, pause, resume, inject_event)
- Frontend: speed selector + pause/play button (persistent UI, not just demo mode)
- Demo mode becomes a YAML scenario rather than hardcoded Python loop
- Enables research "research mode": seed/replay for scenario reproducibility

**Effort:** ~2.5 days | **Unlock:** training mode vs. demo mode distinction; reproducible research; DARPA testbed suitability

### 5B: Weather + Electronic Warfare Engine (10 — Missing Modules)
- `WeatherEngine` — dynamic weather fronts, precipitation, visibility degradation; activates existing `EnvironmentConditions` dataclass
- `WeatherEngine.tick()` — updates conditions per tick; integrates with `sensor_model.py` weather penalty
- `JammerModel` — EW effects on sensor fusion weights; enemy JAMMING UAV type now actually degrades sensor confidence in-zone
- `EWEnvironment` — tracks active jamming zones, GPS spoofing areas
- YAML scenario scripting integration: `SetWeather`, `ActivateJammer` event types
- Wire into ISR priority: autopilot prefers SAR drones when weather degrades EO/IR
- 20+ tests covering weather degradation effects on sensor detection Pd

**Effort:** ~2 days | **Unlock:** simulation realism for autopilot stress-testing; sensor modality switching in degraded conditions

### 5C: Logistics Module (10 — Missing Modules)
- `UAVLogistics` — fuel (depletes by mode/speed), ammunition (decrements on engagement), maintenance state
- `LogisticsManager` — monitors all UAVs; triggers RTB when fuel below threshold; blocks INTERCEPT when ammo zero
- Wire into swarm coordinator: filter assignments by fuel threshold
- Wire into RTB mode in `UAVPhysicsEngine`: use actual base coordinates (fix placeholder)
- Frontend: fuel gauge per drone card; low-fuel system-wide alert in global alert center
- YAML theater config: `base_location` coordinates for RTB destination

**Effort:** ~2 days | **Unlock:** resource constraints force real triage decisions in autonomous mode; RTB is complete; simulation is realistic

### 5D: Terrain Analysis (10 — Missing Modules)
- `TerrainModel` — load elevation data (GeoTIFF via rasterio or simplified DEM); LOS calculations
- `DeadZoneMap` — identify sensor coverage dead zones from terrain masking
- Wire into `sensor_model.py`: apply terrain LOS penalty to Pd calculation
- Wire into `swarm_coordinator.py`: prefer drones with LOS to target gaps
- Theater YAML: reference to DEM file or use simplified grid elevation
- Integrate with Cesium TERRAIN map mode (frontend already has terrain layer)

**Effort:** ~3 days (rasterio/DEM processing is complex) | **Unlock:** sensor coverage realism; autopilot routes drones around terrain obstructions

### 5E: Multi-User RBAC + Authentication (10 — Missing Modules, 08 — Security)
- `UserSession` — JWT auth on WebSocket IDENTIFY message
- `RBACGate` — permission table per WebSocket action: OPERATOR / COMMANDER / ANALYST / ADMIN
- `POST /api/auth/login` — issue JWT
- WebSocket: reject actions the client's role doesn't permit (e.g., ANALYST cannot AUTHORIZE_COA)
- Separate SIMULATOR auth token from DASHBOARD token
- Frontend: login screen, role badge in header
- Wire into audit trail: operator_identity from JWT claims

**Effort:** ~2.5 days | **Unlock:** multi-station deployment; closes CRITICAL security gap (no auth); procurement requirement

---

**Wave 5 Total Estimated Effort:** ~12 person-days (5A + 5B + 5C + 5D + 5E can largely run in parallel; 5D is longer)

**What Wave 5 Enables:**
- CoT/ATAK bridge (Wave 6A) needs auth to know which events are publishable
- RL training environment (Wave 6B) needs scenario scripting and logistics for realistic training
- Full procurement readiness package (auth + audit + ROE + RBAC + XAI)

---

## Wave 6 — Interoperability, Advanced AI, and Production Hardening (Depends on Wave 5)

### 6A: CoT/TAK Bridge + MIL-STD-2525 Symbology (13 — Libraries, 15 — Best Practices, 14 — User Needs)
- `cot_bridge.py` — bidirectional CoT XML translator (PyTAK)
  - VERIFIED targets → CoT hostile events, broadcast on port 8089
  - Subscribe to incoming CoT tracks from ATAK/WinTAK/allied sensors
- MIL-STD-2525 SIDC encoding in `ontology.py`
- Frontend: milsymbol.js or JMSML SVG rendering for standard NATO symbology
- FreeTAKServer Docker sidecar in `docker-compose.yml`
- Protocol version field on all WebSocket messages; OpenAPI spec published

**Effort:** ~3 days | **Unlock:** entire TAK ecosystem interoperability; coalition partner integration; procurement differentiator vs. every competitor

### 6B: RL Training Environment (13 — Libraries, 12 — Research)
- Wrap `SimulationOrchestrator` as PettingZoo `ParallelEnv`
  - Observation space: sensor fusion state per drone
  - Action space: maps to existing WebSocket commands
  - Reward function: target verification rate, kill chain latency, override rate
- Train baseline swarm policy via behavioral cloning from operator session logs (imitation learning)
- Forward simulation branches: before committing to a COA, run N-tick lookahead in a cloned sim, select best outcome
- Expose `step()` / `reset()` interface for external RL training loops

**Effort:** ~5 days | **Unlock:** self-improving autopilot; academic research platform (OpenAI Gym compatible); MARL policy training

### 6C: Frontend Testing (06 — Testing)
- Add Vitest + @testing-library/react to frontend
- Port Playwright E2E from legacy vanilla JS to React frontend
  - WS connects, Cesium globe renders, drone tracks update
  - HITL toasts appear and can be approved/rejected
  - COA panels populate, keyboard shortcuts work
  - Pre-autonomy briefing appears on AUTONOMOUS toggle
- Add to CI: frontend unit + E2E on every PR

**Effort:** ~3 days | **Unlock:** frontend regressions caught in CI; E2E validates full stack

### 6D: Observability + Production Hardening (09 — DevEx, 15 — Best Practices)
- Prometheus metrics endpoint: tick duration, fusion latency, active clients, queue depth
- OpenTelemetry traces for agent pipeline spans
- WebSocket delta encoding: send only changed fields, not full state each tick (50-80% bandwidth reduction)
- SampledPositionProperty pruning in frontend: cap at 600 samples (60s at 10Hz) per drone
- Frontend latency indicator: display WebSocket message age in header
- CORS origins: move to `Grid-SentinelSettings`, support multiple origins
- TLS support in FastAPI (uvicorn SSL config)
- NVIS night-operations mode in frontend (N key, green-dominant low-luminance CSS theme)
- Color-blind accessibility mode (shape+icon redundancy alongside color coding)

**Effort:** ~2.5 days | **Unlock:** production-deployable; observable; accessible for procurement contexts

---

**Wave 6 Total Estimated Effort:** ~14 person-days (6A + 6C + 6D can run in parallel; 6B is longer and somewhat independent)

---

## Autopilot Fast Path — Fastest Route to Production-Quality Autonomous C2

The items on the critical path for a procurement-quality `/autopilot` system, in minimum sequence:

```
Week 1:
  Wave 1 (all parallel, ~2 days wall-clock with team)
    → SCANNING bug fixed
    → CI running
    → Security baseline
    → Performance quick-wins

Week 2-3:
  Wave 2A + 2B in parallel (~3 days wall-clock)
  Wave 2C after 2B (~1 day)
    → Autopilot is testable and behavior-locked
    → Architecture is clean for what follows

Week 4-5:
  Wave 3A (ROE engine) + 3C (Kalman fusion) + 3D (swarm upgrade) + 3E (audit trail) in parallel
  Wave 3B (persistence) sequential but can start concurrently with schema design
    → Autonomous mode is rule-bounded
    → Every autonomous action is logged
    → Swarm is resilient and autonomy-level-aware

Week 6-7:
  Wave 4A (XAI reasoning) + 4B (per-action autonomy) + 4C (confidence-gated authority) + 4D (alert center) in parallel
  Wave 4E (AAR) after 3B completes
    → DoD 3000.09 compliance: XAI, pre-autonomy briefing, audit trail, per-action controls
    → Procurement-demonstrable system
    → System has closed feedback loop for tuning

Week 8-9:
  Wave 5E (RBAC/auth) — closes last CRITICAL security gap
  Wave 5A (scenario scripting) for research testbed value
    → Multi-user secure deployment
    → Reproducible research scenarios
```

**Total fast-path estimate: ~9 weeks with 2-3 parallel engineers**

The non-fast-path items (terrain analysis, EW, logistics, RL, CoT bridge) can proceed concurrently after Week 5 without blocking the autonomy path.

---

## Priority Matrix by Category

| Category | Wave | Items | Blocks Autopilot? |
|----------|------|-------|-------------------|
| Critical bug fixes | 1A | SCANNING, dead branch, blocking input() | YES — autopilot broken without |
| DevEx / CI | 1B | pyproject, pre-commit, GitHub Actions | YES — refactors unsafe without |
| Security baseline | 1C | message size, HITL replay, input validation | YES — CRITICAL gaps |
| Performance quick-wins | 1D | get_state cache, dict lookups, event logger | No (but enables scale) |
| Test infrastructure | 1E | Hypothesis, Locust, payload tests, autopilot tests | YES — required before refactor |
| sim_engine split | 2A | UAVPhysicsEngine, etc. | YES — enables clean AutonomyController |
| api_main split | 2B | autopilot.py, handlers, loop | YES — autopilot untestable without |
| Autopilot tests | 2C | 10 autopilot behavior tests | YES — behavior locked down |
| Docker | 2D | Dockerfiles, compose | No (but enables CI E2E) |
| ROE Engine | 3A | ROEEngine, theater YAML | YES — deterministic safety constraint |
| Persistence | 3B | MissionStore, StrikeArchive | Partially (enables AAR + audit) |
| Kalman sensor fusion | 3C | FilterPy UKF tracks | No (but improves confidence accuracy) |
| Swarm upgrade | 3D | Hungarian, anomaly detection, promotion | Partially (resilience in auto mode) |
| Audit trail | 3E | Structured logs, REST endpoint, override codes | YES — DoD 3000.09 requirement |
| XAI reasoning panel | 4A | Chain-of-thought, "Why?" button, source labels | YES — operator trust + compliance |
| Per-action autonomy | 4B | Action matrix, time-bounded grants, briefing screen | YES — disciplined autonomy |
| Confidence-gated authority | 4C | Dynamic escalation, vigilance prompts | YES — prevents inadvertent escalation |
| UX critical fixes | 4D | Global alerts, strike board overlay, shortcuts | YES — operators miss approval windows |
| AAR engine | 4E | Replay, decision timeline, metrics export | No (but critical for tuning) |
| Scenario scripting | 5A | YAML scripts, SimController | No (research testbed) |
| Weather + EW | 5B | WeatherEngine, JammerModel | No (realism) |
| Logistics | 5C | Fuel, ammo, RTB fix | No (realistic constraints) |
| Terrain analysis | 5D | LOS, dead zones | No (sensor realism) |
| RBAC + Auth | 5E | JWT, RBACGate, login | YES — CRITICAL for multi-user |
| CoT/TAK bridge | 6A | PyTAK, MIL-STD-2525 | No (interoperability) |
| RL environment | 6B | PettingZoo, behavioral cloning | No (self-improvement) |
| Frontend testing | 6C | Vitest, Playwright React | No (quality gate) |
| Observability | 6D | Prometheus, delta encoding, NVIS mode | No (production hardening) |

---

## Open Research Opportunities

Per 12_research.md, Grid-Sentinel is positioned to lead in three areas no competitor has addressed:

1. **End-to-end F2T2EA autopilot benchmark** — No public benchmark exists. After Wave 4, expose a research API and publish scenario packs.

2. **LLM + swarm coordination integration** — After Wave 3D (Hungarian swarm) + 4A (XAI), Grid-Sentinel uniquely combines LLM reasoning with optimal assignment. Log the delta between LLM recommendation and Hungarian solution to build a training dataset.

3. **Adaptive sensor fusion under EW** — After Wave 5B (EW engine) + 3C (Kalman fusion), run studies on how fusion degrades gracefully under selective jamming. Grid-Sentinel's multi-sensor model is uniquely suited.
