# Palantir Implementation Roadmap

**Author:** Roadmap Designer (Agent 22)
**Date:** 2026-03-20
**Source:** Discussions 01–20, CHECKPOINT.md, PROJECT_BRIEF.md

---

## Overview

This roadmap organizes 87 proposals from the brainstorm into five phases with parallel tracks within each phase. Phases are sequential — each phase depends on the prior one — but tracks within a phase can execute concurrently.

**Total estimated effort:** ~65 person-days (~13 weeks with 1 engineer, ~5 weeks with 3 parallel engineers)

**Critical path:** Phase 1 -> Phase 2 -> Phase 3 ROE/Audit -> Phase 4 XAI/Autonomy -> Phase 5 Auth/Interop

---

## Phase 1: Foundation & Critical Fixes

**Goal:** Make the system correct, safe to demo, and safe to refactor.
**Duration:** ~6 person-days (1-2 weeks wall-clock with parallelism)
**Dependencies:** None — this is the starting point.

### Track 1A: Critical Bug Fixes (~1 day)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| F-001 | Fix `"SCANNING"` -> `"SEARCH"` in autopilot dispatch | `api_main.py` | ~2 | 0.1d |
| F-002 | Fix dead `"DESTROYED"` branch / unbounded `enemy_intercept_dispatched` | `api_main.py` | ~10 | 0.1d |
| F-005 | Replace `except ValueError: pass` with `logger.exception()` | `api_main.py` | ~10 | 0.1d |
| F-003 | Implement `_generate_response()` in 3 NotImplementedError agents | `battlespace_manager.py`, `pattern_analyzer.py`, `synthesis_query_agent.py` | ~150 | 0.5d |
| F-004 | Replace blocking `input()` in `pipeline.py` | `pipeline.py` | ~10 | 0.1d |
| F-015 | Fix `_nominated` set memory leak (add TTL/cap) | `api_main.py` | ~10 | 0.1d |

**Success criteria:** `./palantir.sh --demo` runs a full F2T2EA cycle with drones dispatching to targets. All agents callable without crash. No silent exception swallowing.

### Track 1B: Security Baseline (~1 day)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| S01 | WebSocket message size guard before `json.loads()` | `api_main.py` | ~10 | 0.1d |
| S02 | HITL replay fix: check `status == "PENDING"` before transition | `hitl_manager.py` | ~10 | 0.1d |
| S03 | Input validation: lat/lon ranges, theater allowlist, coverage_mode allowlist, subscribe element types, SITREP length limit | `api_main.py` | ~100 | 0.3d |
| SEC02 | Demo autopilot circuit breaker: max N auto-approvals, halt if no DASHBOARD | `api_main.py` | ~40 | 0.2d |
| F-016 | Fix `verify_target` handler bypassing verification engine | `api_main.py` | ~20 | 0.1d |

**Success criteria:** No CRITICAL or HIGH security findings from 08_security.md remain. HITL replay attack closed. Input validation covers all WebSocket actions.

### Track 1C: Performance Quick Wins (~0.5 day)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| A01 | Cache `get_state()` once per tick | `api_main.py` | ~15 | 0.1d |
| A02 | Replace `_find_uav/target/enemy_uav` O(N) scans with dict lookups | `sim_engine.py`, `api_main.py` | ~50 | 0.2d |
| A03 | Move `build_isr_queue()` into assessment thread | `api_main.py` | ~5 | 0.05d |
| A04 | Fix event logger: keep file handle open | `event_logger.py` | ~20 | 0.1d |
| PERF03 | Prune SampledPositionProperty in frontend (cap 600 samples) | Cesium hooks | ~20 | 0.1d |

**Success criteria:** 10Hz tick loop stable at 50 UAVs + 50 targets. `get_state()` called once per tick. O(1) entity lookups.

### Track 1D: DevEx & CI Infrastructure (~1.5 days)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| D01 | `pyproject.toml` with pinned deps, ruff/mypy/pytest config | `pyproject.toml`, `requirements.txt` | ~80 | 0.3d |
| D02 | `.pre-commit-config.yaml` (black, ruff, mypy, eslint) | `.pre-commit-config.yaml` | ~40 | 0.2d |
| D03 | GitHub Actions CI: pytest + ruff + coverage 80% gate | `.github/workflows/test.yml` | ~150 | 0.5d |
| INFRA02 | `/health` and `/ready` endpoints | `api_main.py` | ~30 | 0.1d |
| INFRA03 | Makefile with setup/run/test/lint targets | `Makefile` | ~60 | 0.1d |

**Success criteria:** Every PR runs lint + tests + coverage. `make test` works from clean checkout. Pre-commit hooks catch formatting violations.

### Track 1E: Test Coverage for Critical Paths (~2 days)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| T01 | Tests for `demo_autopilot()` (10 scenarios) | `tests/test_autopilot.py` | ~200 | 0.5d |
| T02 | Tests for `tactical_planner.py` COA generation | `tests/test_tactical_planner.py` | ~150 | 0.3d |
| T03 | Tests for all `handle_payload()` branches (~20 action types) | `tests/test_handlers.py` | ~300 | 0.5d |
| TEST01 | `hypothesis` property-based tests for pure-function invariants | `tests/test_*_property.py` | ~150 | 0.3d |
| LIB04 | Locust WebSocket load test (50 concurrent clients) | `tests/load/locustfile.py` | ~100 | 0.2d |

**Success criteria:** Coverage reaches 80%+ across all Python files. Autopilot dispatch, COA generation, and all WebSocket handlers have test coverage. Property tests validate sensor fusion in [0,1], verification never regresses, swarm never double-assigns.

### Track 1F: Library Additions (~0.5 day)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| LIB01 | Add `shapely` for backend geometry (zone math) | `battlespace_assessment.py` | ~30 | 0.1d |
| LIB02 | Add `turf.js` for frontend geospatial (replace inline trig) | Cesium hooks | ~50 | 0.2d |
| ALGO01 | Replace O(n^2) clustering with `scipy.spatial.KDTree` | `battlespace_assessment.py` | ~30 | 0.1d |
| -- | Add `filterpy`, `scipy` to requirements (prototype-ready) | `requirements.txt` | ~5 | 0.05d |

**Success criteria:** `shapely` and `turf.js` integrated. KD-tree clustering operational. FilterPy and scipy available for Phase 2.

### Phase 1 Parallel Execution Map

```
Week 1:
  Track 1A ---------  (1d)     <- Bug fixes, all independent
  Track 1B ---------  (1d)     <- Security, all independent
  Track 1C --------   (0.5d)   <- Performance, all independent
  Track 1D ------------------- (1.5d) <- DevEx/CI
  Track 1E -------------------------- (2d) <- Tests (longest track)
  Track 1F --------   (0.5d)   <- Libraries
```

All tracks are fully independent. With 3 engineers: ~2 days wall-clock.

---

## Phase 2: Core Capability Upgrades

**Goal:** Clean architecture enabling future work. Testable autopilot. Algorithm fidelity.
**Duration:** ~14 person-days (2-3 weeks wall-clock)
**Dependencies:** Phase 1 complete (tests exist as safety net for refactoring)

### Track 2A: Split sim_engine.py God Module (~3 days)

Extract `SimulationModel` (1,553 lines) into domain services:

| New Module | Responsibility | Approx LOC |
|------------|---------------|------------|
| `uav_physics.py` | 11 UAV modes, turn rate, orbit, RTB navigation | ~350 |
| `target_behavior.py` | 5 target archetypes, emit toggle, shoot-and-scoot | ~200 |
| `enemy_uav_engine.py` | 4 enemy UAV modes, intercept confidence | ~150 |
| `detection_pipeline.py` | Sensor detection O(U*T*S), FOV computation | ~200 |
| `autonomy_controller.py` | AUTONOMOUS_TRANSITIONS table, mode promotion | ~100 |
| `sim_orchestrator.py` | Thin tick() loop coordinating all engines | ~150 |

Also fixes inside this refactor:
- F-006: RTB mode -- real destination from theater config (replace drift placeholder)
- F-008: Vision processor hardcoded Bristol coordinates
- F-018: Autonomy level preserved across theater switches
- `altitude_penalty` in sensor_model.py: apply documented but unused variable

**Success criteria:** All 475 existing tests pass. Each engine has its own test file. `sim_engine.py` removed or reduced to re-exports. No module exceeds 400 lines.

### Track 2B: Split api_main.py God File (~3 days)

Extract `api_main.py` (1,113 lines) into modules:

| New Module | Responsibility | Approx LOC |
|------------|---------------|------------|
| `websocket_manager.py` | Connection tracking, broadcast, auth | ~150 |
| `simulation_loop.py` | 10Hz tick, assessment scheduling | ~150 |
| `autopilot.py` | `AutopilotController` class, injectable deps | ~250 |
| `action_handlers/` | Command registry + handler modules | ~300 |
| `tactical_assistant.py` | Standalone TacticalAssistant class | ~150 |
| `api_main.py` | Thin assembly: FastAPI app, route registration | ~100 |

Also fixes inside this refactor:
- F-011: Command dispatch table (replace 200-line if/elif)
- F-012: asyncio data race (snapshot before `to_thread`)
- F-013: `demo_autopilot()` decoupled from WebSocket globals
- F-014: Magic constants -> `PalantirSettings`
- CORS origins moved to config

**Success criteria:** `autopilot.py` testable with AsyncMock (no WebSocket required). All action handlers individually testable. Data race eliminated. No module exceeds 400 lines.

### Track 2C: Autopilot Test Suite (~1 day, after 2B)

Now that autopilot is decoupled, add comprehensive behavioral tests:

| Test | What It Validates |
|------|-------------------|
| `test_autopilot_approves_pending_after_delay` | HITL timeout behavior |
| `test_autopilot_dispatches_nearest_search_uav` | SCANNING fix from Phase 1 |
| `test_autopilot_escalates_follow_to_paint` | Mode progression |
| `test_autopilot_generates_coas_after_paint` | COA pipeline |
| `test_autopilot_authorizes_best_coa` | COA selection |
| `test_autopilot_auto_intercepts_enemy` | Enemy response |
| `test_full_kill_chain_completes` | End-to-end DETECTED->ENGAGED |
| `test_supervised_requires_approval` | HITL gate enforcement |
| `test_circuit_breaker_halts_runaway` | Safety guard |
| `test_autonomous_with_manual_override` | Override handling |

**Success criteria:** 10 autopilot behavioral tests passing in CI. Kill chain integration test covers full DETECTED->AUTHORIZED flow.

### Track 2D: Algorithm Fidelity (~3 days)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| ALGO04 | RTB real destination (theater base coords) | `uav_physics.py`, `theaters/*.yaml` | ~80 | 0.3d |
| ALGO02 | Kalman track fusion (FilterPy UKF per target) | `sensor_fusion.py` | ~400 | 1.5d |
| ALGO03 | Hungarian algorithm for swarm assignment | `swarm_coordinator.py` | ~200 | 0.5d |
| ALGO07 | Proper radar range equation (1/R^4 Nathanson) | `sensor_model.py`, `theaters/*.yaml` | ~200 | 0.5d |
| F-017 | Swarm coordinator autonomy level awareness | `swarm_coordinator.py` | ~100 | 0.3d |

**Success criteria:** Kalman fusion provides position uncertainty bounds per target. Hungarian assignment provably optimal. Sensor detection physically grounded. Swarm respects autonomy level.

### Track 2E: Docker & Infrastructure (~1 day)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| INFRA01 | `Dockerfile.backend` (Python 3.12 slim + opencv) | `Dockerfile.backend` | ~40 | 0.2d |
| -- | `Dockerfile.frontend` (node:20 + nginx) | `Dockerfile.frontend` | ~30 | 0.1d |
| -- | `docker-compose.yml` (backend + frontend + simulator) | `docker-compose.yml` | ~80 | 0.2d |
| -- | CI: build + smoke-test containers | `.github/workflows/` | ~50 | 0.2d |
| DOC01 | OpenAPI spec for WebSocket protocol | `docs/websocket_protocol.md` | ~200 | 0.3d |

**Success criteria:** `docker-compose up` brings up full stack. CI validates container build. WebSocket protocol documented.

### Track 2F: Frontend Quick Wins (~2 days)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| UX03 | Confirmation dialog before AUTONOMOUS | 1 component | ~60 | 0.2d |
| UX04 | Fix dead buttons (Range, Detail) | 1 file | ~30 | 0.1d |
| UX08 | Keyboard shortcuts (A/R approve/reject, Esc=MANUAL) | 1 file | ~60 | 0.2d |
| UX15 | Night operations display mode (NVIS, N key) | 2 files | ~100 | 0.3d |
| UX05 | F2T2EA phase indicator per target | 2 files | ~200 | 0.3d |
| UX18 | WebSocket latency indicator in header | 1 file | ~50 | 0.1d |
| UX09 | ISR Queue one-click dispatch | 2 files | ~100 | 0.2d |

**Success criteria:** AUTONOMOUS toggle requires explicit confirmation. Dead buttons functional. Keyboard shortcuts operational. Night mode available.

### Phase 2 Parallel Execution Map

```
Week 3-4:
  Track 2A ------------------- (3d) <- sim_engine split
  Track 2B ------------------- (3d) <- api_main split
  Track 2D ------------------- (3d) <- Algorithm upgrades
  Track 2E ---------  (1d)          <- Docker
  Track 2F -------------- (2d)      <- Frontend UX
                    Track 2C ------ (1d, after 2B)  <- Autopilot tests
```

Tracks 2A, 2B, 2D, 2E, 2F are independent. 2C waits for 2B. With 3 engineers: ~2 weeks wall-clock.

---

## Phase 3: New Modules & Subsystems

**Goal:** Add the highest-impact missing capabilities that enable procurement readiness.
**Duration:** ~16 person-days (2-3 weeks wall-clock)
**Dependencies:** Phase 2 complete (clean architecture, testable autopilot, dict-based entities)

### Track 3A: ROE Engine (~2 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `roe_engine.py` | `ROERule` dataclass, `ROEEngine.evaluate()`, `ROEDecision` enum | ~300 |
| `theaters/roe/*.yaml` | Declarative rules per theater | ~100 |
| Integration | Wire into `autonomy_controller.py` (veto in AUTONOMOUS), `strategy_analyst.py` (advisory only), `autopilot.py` (pre-nomination check) | ~200 |
| Tests | 30+ unit tests: all rule combos, escalation, veto | ~200 |

**Dependencies:** Track 2A (AutonomyController), Track 2B (autopilot module)
**Success criteria:** ROE engine blocks prohibited engagements in AUTONOMOUS mode. LLM recommendations that violate ROE are vetoed. Rules are YAML-configurable per theater.

### Track 3B: Structured Audit Trail (~1.5 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `audit_log.py` | Structured `AuditRecord`: timestamp, action_type, autonomy_level, sensor_evidence, hitl_status, operator_identity | ~200 |
| Override capture | Reason codes (WRONG_TARGET / WRONG_TIMING / ROE_VIOLATION) on reject | ~100 |
| REST endpoint | `GET /api/audit` with time/action/level filters | ~80 |
| Hash chain | SHA-256 append-only tamper-evident log | ~60 |
| Override -> prompt | Feed override reasons into TacticalAssistant context | ~40 |

**Dependencies:** Track 1C (event logger fix), Track 2B (action handlers)
**Success criteria:** Every autonomous action logged with full evidence chain. Override reason codes captured. REST endpoint returns filtered audit records. Hash chain validates integrity.

### Track 3C: AI Explainability Layer (~2 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `DecisionExplanation` model | Structured trace: action, source (LLM/heuristic), top-3 factors, ROE rule, alternatives, counterfactual threshold | ~100 |
| `TacticalAssistant` upgrade | Chain-of-thought prompting, structured JSON output | ~100 |
| `ExplainabilityStore` | Log all explanations, queryable by target/time | ~100 |
| Backend integration | Attach explanation to every `StrikeBoardEntry` and `HitlNomination` | ~100 |
| Frontend `ExplanationPanel.tsx` | "Why?" expandable on every HITL entry, source label [AI: Gemini] / [Heuristic: Rule N] | ~200 |

**Dependencies:** Track 1A (agents functional -- F-003), Track 3A (ROE engine provides rule IDs)
**Success criteria:** Every AI recommendation has structured explanation. "Why?" button on all HITL entries. Source (LLM vs heuristic) clearly labeled. Counterfactual thresholds displayed.

### Track 3D: Persistence Layer (~3 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `persistence/mission_store.py` | SQLite dev / PostgreSQL prod, async via SQLAlchemy | ~300 |
| `persistence/models.py` | Schema: target_events, drone_assignments, engagements, operator_actions | ~200 |
| `persistence/checkpoint.py` | Full state snapshot on demand | ~150 |
| WebSocket actions | `save_checkpoint`, `load_mission`, `list_missions` | ~100 |
| REST endpoints | `GET /api/missions`, `GET /api/missions/{id}`, `POST /api/missions/{id}/restore` | ~100 |
| Alembic migrations | Schema versioning | ~100 |

**Dependencies:** Track 2B (clean handler registration), Track 2A (SimOrchestrator state serializable)
**Success criteria:** Mission state survives backend restart. Checkpoint/restore operational. Mission list queryable via REST. Async DB access (no event loop blocking).

### Track 3E: Simulation Fidelity Controls (~1.5 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `SimController` | pause/resume, 1x-50x speed, single-step mode | ~150 |
| WebSocket action | `sim_control` (speed, pause, resume, step, inject_event) | ~80 |
| Frontend | Speed selector, pause/play button, step button | ~150 |
| Integration | `simulation_loop.py` checks `SimController` each tick | ~30 |

**Dependencies:** Track 2B (simulation_loop.py extracted)
**Success criteria:** Pause/resume working via UI and WebSocket. Speed compression 1x-50x. Single-step mode for debugging. Frontend controls visible in all tabs.

### Track 3F: UX Safety & Alerting (~2 days)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| UX01 | Global alert center overlay (critical events across all tabs) | 3 files | ~300 | 0.5d |
| UX02 | Strike board floating overlay (always visible) | 2 files | ~200 | 0.3d |
| UX06 | AI decision explanation panel (consumes Track 3C) | 2 files | ~250 | 0.3d |
| UX07 | Pre-autonomy briefing screen (ROE state, what auto-approves) | 1 file | ~100 | 0.2d |
| UX16 | Override capture + reason code UI | 3 files | ~150 | 0.2d |
| UX17 | AI recommendation acceptance rate display | 2 files | ~100 | 0.2d |
| UX10 | Map right-click context menu | 2 files | ~200 | 0.3d |

**Dependencies:** Track 3A (ROE for briefing screen), Track 3B (audit for acceptance rate), Track 3C (explanations for panel)
**Success criteria:** Critical alerts visible across all tabs. Strike board never buried. Pre-autonomy briefing requires acknowledgment. Override reasons captured in UI.

### Track 3G: Testing Infrastructure Expansion (~2 days)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| TEST02 | Full kill chain integration test (DETECTED->ENGAGED) | 1 file | ~200 | 0.5d |
| TEST06 | Monte Carlo benchmark scenarios (Pd, latency, override rate) | 2 files | ~200 | 0.3d |
| LIB03 | Hypothesis advanced: ROE rule exhaustive, fusion invariants | 3 files | ~150 | 0.3d |
| TEST04 | Vitest + React Testing Library setup for frontend | 5 files | ~500 | 0.5d |
| -- | Coverage gate: maintain 80%+ with new modules | CI config | ~20 | 0.1d |

**Dependencies:** Phase 2 tests as foundation
**Success criteria:** Kill chain integration test covers full pipeline. Monte Carlo benchmarks baseline Pd, latency, override metrics. Frontend unit test framework operational.

### Phase 3 Parallel Execution Map

```
Week 5-7:
  Track 3A -------------- (2d)   <- ROE Engine
  Track 3B ------------ (1.5d)   <- Audit Trail
  Track 3C -------------- (2d)   <- XAI Layer
  Track 3D ------------------- (3d) <- Persistence (longest)
  Track 3E ------------ (1.5d)   <- Sim Controls
  Track 3G -------------- (2d)   <- Testing
              Track 3F -------------- (2d, after 3A+3B+3C) <- UX
```

Tracks 3A-3E and 3G are independent. Track 3F waits for 3A, 3B, 3C outputs. With 3 engineers: ~2.5 weeks wall-clock.

---

## Phase 4: Advanced Features & Integration

**Goal:** Autonomy model upgrade, environmental fidelity, multi-user security, interoperability.
**Duration:** ~16 person-days (2-3 weeks wall-clock)
**Dependencies:** Phase 3 complete (ROE engine, persistence, audit trail, XAI)

### Track 4A: Per-Action Autonomy Matrix + Confidence Gating (~3 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `AutonomyPolicy` Pydantic model | Per-action levels: FOLLOW, PAINT, INTERCEPT, AUTHORIZE_COA, ENGAGE each get independent autonomy level | ~100 |
| Time-bounded grants | `duration_seconds` + `exception_conditions`, auto-revert | ~100 |
| Confidence gating | In AUTONOMOUS, escalate to operator when AI confidence < threshold (default 0.80) | ~150 |
| Vigilance prompts | Periodic UI acknowledgment in SUPERVISED/AUTONOMOUS to prevent complacency | ~80 |
| Frontend policy editor | Autonomy grant UI with countdown timers per active grant | ~250 |
| Frontend confidence UI | Amber glow on low-confidence actions in strike board | ~80 |

**Dependencies:** Track 3A (ROE engine), Track 2A (AutonomyController), Track 3C (confidence scores)
**Success criteria:** Operators can set "follow autonomously, ask before engaging." Time-bounded grants auto-revert. Low-confidence decisions escalate even in AUTONOMOUS mode. Vigilance prompts prevent complacency.

### Track 4B: After-Action Review Engine (~3 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `aar_engine.py` | Variable-speed replay (1x-50x) from persisted snapshots | ~300 |
| `DecisionTimeline` | Events by F2T2EA phase with timestamps | ~150 |
| AI vs operator comparison | Where autopilot would have differed from human decisions | ~100 |
| AAR report generator | Kill chain latency, fusion accuracy, override rate, COA accuracy | ~150 |
| Frontend AAR tab | Timeline scrubber, speed selector, filter by drone/target/action | ~400 |
| Export | Mission report JSON/CSV/kepler.gl format | ~100 |

**Dependencies:** Track 3D (persistence -- stored mission snapshots), Track 3B (audit trail -- decision records)
**Success criteria:** Mission replay at variable speed. Decision timeline shows AI vs operator choices. Structured AAR report exportable. Timeline scrubber in new REPLAY tab.

### Track 4C: Weather + Electronic Warfare (~2.5 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `weather_engine.py` | `WeatherEngine.tick()`: moving fronts, precipitation, clearing | ~200 |
| Sensor integration | Dynamic sensor weights based on weather conditions | ~80 |
| `ew_module.py` | `JammerModel`: spatial radius, frequency attenuation | ~250 |
| GPS spoofing | Position error for affected UAVs | ~60 |
| Comms degradation | Message delay/drop for affected clients | ~40 |
| Fusion integration | Reduce weights for jammed sensor types | ~40 |
| Frontend | Weather indicator, jamming warnings in Intel Feed | ~100 |

**Dependencies:** Track 2A (DetectionPipeline extracted), Track 2D (sensor model upgraded)
**Success criteria:** Weather changes dynamically during mission. Sensor effectiveness varies with weather. Jamming UAVs actually degrade sensor confidence. EW warnings in Intel Feed.

### Track 4D: Logistics Module (~2 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `UAVLogistics` dataclass | fuel (depletes by mode/speed), ammo (decrements on engagement), maintenance | ~100 |
| `LogisticsManager` | Monitor fleet, trigger RTB on low fuel, block INTERCEPT on zero ammo | ~150 |
| Swarm integration | Filter assignments by fuel threshold | ~50 |
| Frontend | Fuel gauge on DroneCard, low-fuel system-wide alert | ~100 |
| Theater config | `base_location` coordinates for RTB destination | ~30 |

**Dependencies:** Track 2A (UAVPhysicsEngine -- RTB logic), Track 2D (ALGO04 -- RTB destination)
**Success criteria:** Drones deplete fuel realistically. Ammo decrements on engagement. RTB auto-triggers on low fuel. Swarm coordinator respects fuel constraints.

### Track 4E: Multi-User Authentication & RBAC (~2.5 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `auth.py` | JWT issuance, WebSocket token auth on IDENTIFY | ~200 |
| `rbac.py` | `RBACGate`: OPERATOR / COMMANDER / ANALYST / ADMIN per action | ~250 |
| `POST /api/auth/login` | Token issuance endpoint | ~50 |
| WebSocket enforcement | Reject actions the client's role doesn't permit | ~100 |
| Frontend | Login screen, role badge in header | ~150 |
| Audit integration | `operator_identity` from JWT claims in audit records | ~30 |

**Dependencies:** Track 1B (input validation), Track 3B (audit trail), Track 2B (action handlers)
**Success criteria:** All endpoints require authentication. ANALYST cannot AUTHORIZE_COA. SIMULATOR auth separate from DASHBOARD. Dev mode bypass via `AUTH_DISABLED=true`. Audit trail includes operator identity.

### Track 4F: Frontend Testing & E2E (~2 days)

| ID | Item | Files | LOC | Effort |
|----|------|-------|-----|--------|
| TEST04 | Vitest component tests for key React components | 10+ test files | ~500 | 0.5d |
| TEST05 | Playwright E2E: WS connect, globe render, HITL flow, shortcuts | 4 test files | ~600 | 1d |
| -- | CI integration: frontend tests on every PR | CI config | ~50 | 0.2d |
| -- | Accessibility audit: color-blind mode, ARIA labels | 5 files | ~100 | 0.3d |

**Dependencies:** Track 3F (UX components exist to test)
**Success criteria:** Playwright E2E validates full stack: connect, render globe, approve HITL, keyboard shortcuts. Frontend CI gate active.

### Phase 4 Parallel Execution Map

```
Week 8-10:
  Track 4A ------------------- (3d)   <- Autonomy matrix + confidence gating
  Track 4B ------------------- (3d)   <- AAR engine
  Track 4C ---------------- (2.5d)    <- Weather + EW
  Track 4D -------------- (2d)        <- Logistics
  Track 4E ---------------- (2.5d)    <- Auth + RBAC
  Track 4F -------------- (2d)        <- Frontend E2E
```

All tracks are independent. With 3 engineers: ~2.5 weeks wall-clock.

---

## Phase 5: Innovation & Research

**Goal:** Cutting-edge capabilities that differentiate Palantir from all competitors.
**Duration:** ~13+ person-days (ongoing, prioritize by research value)
**Dependencies:** Phases 1-4 complete

### Track 5A: Interoperability -- CoT/TAK Bridge + MIL-STD-2525 (~3 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `cot_bridge.py` | Bidirectional CoT XML translator (PyTAK) | ~250 |
| CoT broadcast | VERIFIED targets -> CoT hostile events on port 8089 | ~100 |
| CoT subscribe | Incoming tracks from ATAK/WinTAK/allied sensors | ~100 |
| MIL-STD-2525 SIDC | Encoding in `ontology.py` | ~50 |
| Frontend symbology | milsymbol.js NATO symbol rendering on Cesium globe | ~200 |
| FreeTAKServer sidecar | Docker Compose addition | ~50 |

**Success criteria:** Palantir publishes VERIFIED targets to TAK ecosystem. Incoming CoT tracks appear on Cesium globe. NATO symbology rendered.

### Track 5B: Terrain Analysis with DEM Integration (~3 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `terrain_model.py` | Load DEM data (GeoTIFF via rasterio), LOS calculations | ~250 |
| `DeadZoneMap` | Pre-compute sensor shadows per UAV altitude | ~150 |
| Sensor integration | Block detections when no LOS | ~60 |
| Swarm integration | Prefer drones with LOS to target gaps | ~50 |
| Frontend | TERRAIN map mode shows coverage shadows from elevation | ~100 |

**Success criteria:** Sensor detection respects terrain. Coverage dead zones visible on map. Swarm prefers LOS positions.

### Track 5C: Forward Simulation for COA Selection (~2 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `SimulationModel.clone()` | Deep copy of current state | ~50 |
| `project_forward(model, ticks)` | Run N ticks on cloned sim | ~100 |
| COA evaluation | Run forward branches per COA candidate, select max-score | ~150 |
| Integration | In `autopilot.py` authorization, use projected outcomes | ~50 |
| Frontend | Display projected outcome in COA rationale | ~50 |

**Success criteria:** COA selection uses simulation-predicted outcomes rather than static heuristic formula. Forward branch runs in background thread.

### Track 5D: Scenario Scripting Engine (~2 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| `scenario_loader.py` | Parse YAML exercise scripts | ~100 |
| `scenario_player.py` | Play scripts: inject events at T+N | ~200 |
| Event types | SpawnTarget, SetWeather, DegradeComms, TriggerEnemyUAV, InjectFalseDetection | ~150 |
| Demo mode migration | Demo becomes a YAML scenario, not hardcoded Python | ~100 |
| Example scenarios | 3 theater-specific training scenarios | ~200 |

**Success criteria:** Demo mode driven by YAML scenario. Custom training exercises creatable without code changes. Scenario reproducible with seed.

### Track 5E: RL Training Environment (~5 days)

| Component | Description | LOC |
|-----------|-------------|-----|
| PettingZoo `ParallelEnv` wrapper | Observation space: fusion state per drone. Action space: WebSocket commands | ~300 |
| Reward function | Target verification rate, kill chain latency, override rate | ~100 |
| Behavioral cloning | Baseline policy from operator session logs | ~200 |
| `step()` / `reset()` interface | External RL training loop compatible | ~100 |
| Evaluation harness | Compare learned policy vs heuristic vs human on benchmark scenarios | ~100 |

**Success criteria:** PettingZoo environment passes `parallel_api_test`. Behavioral cloning produces baseline policy. OpenAI Gym-compatible interface for external training.

### Track 5F: Advanced Algorithms (Research Grade) (~3+ days)

| ID | Item | Effort | Risk |
|----|------|--------|------|
| ALGO06 | Bayesian belief state per target (replaces FSM -- HIGH RISK) | 3d | high |
| ALGO08 | Hierarchical dynamic authority (confidence-gated escalation chains) | 3d | medium |
| ALGO09 | Raft consensus for swarm assignment (Byzantine fault-tolerant) | 3d | high |
| ALGO10 | Forward simulation branches for COA selection (digital twin) | 2d | high |
| F-025 | BDI target behavior model | 2d | medium |
| F-029 | 3-DOF UAV kinematics with wind model | 2d | medium |

**Note:** ALGO06 (Bayesian belief) carries HIGH risk -- it replaces the well-tested verification FSM. Recommend deferring unless research publication is a goal. Improve thresholds on existing FSM instead.

### Track 5G: Production Hardening (~2 days)

| ID | Item | Effort |
|----|------|--------|
| PERF02 | WebSocket delta compression (50-80% bandwidth reduction) | 0.5d |
| SEC04 | LLM prompt injection prevention | 0.3d |
| SEC05 | TLS enforcement + origin checking | 0.3d |
| -- | Prometheus metrics endpoint | 0.3d |
| -- | OpenTelemetry traces for agent pipeline | 0.3d |
| -- | Color-blind accessibility mode | 0.2d |

**Success criteria:** Delta compression reduces bandwidth. TLS available. Observability endpoints operational.

### Phase 5 Execution Notes

Phase 5 tracks are largely independent and should be prioritized by organizational goals:

- **Procurement focus:** 5A (interop) + 5G (hardening) first
- **Research focus:** 5C (forward sim) + 5E (RL) + 5F (algorithms) first
- **Realism focus:** 5B (terrain) + 5D (scenarios) first

---

## Cross-Phase Dependency Summary

```
Phase 1 (Foundation)
  |-- All tracks independent, maximum parallelism
  \-- Unlocks: safe refactoring, CI quality gates, correct autopilot

Phase 2 (Core Upgrades)
  |-- 2A (sim split) + 2B (api split) + 2D (algos) + 2E (docker) + 2F (UX) -- parallel
  |-- 2C (autopilot tests) -- after 2B
  \-- Unlocks: clean architecture, testable autopilot, algorithm fidelity

Phase 3 (New Modules)
  |-- 3A (ROE) + 3B (audit) + 3C (XAI) + 3D (persistence) + 3E (sim controls) + 3G (tests) -- parallel
  |-- 3F (UX safety) -- after 3A, 3B, 3C
  \-- Unlocks: procurement compliance, operator trust, mission persistence

Phase 4 (Advanced Features)
  |-- 4A (autonomy) + 4B (AAR) + 4C (weather/EW) + 4D (logistics) + 4E (auth) + 4F (E2E) -- parallel
  \-- Unlocks: full autonomy model, environmental fidelity, multi-user security

Phase 5 (Innovation)
  |-- All tracks independent, prioritize by organizational goal
  \-- Unlocks: interoperability, RL training, terrain realism, research platform
```

---

## Effort Summary

| Phase | Person-Days | Wall-Clock (3 engineers) | Key Deliverable |
|-------|-------------|--------------------------|-----------------|
| Phase 1 | 6 | ~2 weeks | Correct, secure, CI-gated codebase |
| Phase 2 | 14 | ~2.5 weeks | Clean architecture, testable autopilot |
| Phase 3 | 16 | ~2.5 weeks | ROE engine, XAI, audit trail, persistence |
| Phase 4 | 16 | ~2.5 weeks | Per-action autonomy, AAR, weather/EW, auth |
| Phase 5 | 13+ | Ongoing | Interop, terrain, RL, research platform |
| **Total** | **~65** | **~10-12 weeks** | **Production-grade autonomous C2** |

---

## Risk Register

| Risk | Phase | Severity | Mitigation |
|------|-------|----------|------------|
| ARCH01/ARCH02 refactors break 475 tests | 2 | HIGH | Phase 1 tests are the safety net; green before starting |
| ALGO06 Bayesian belief invalidates all verification code | 5 | HIGH | Mark as optional; improve thresholds on existing FSM |
| Persistence layer blocks event loop (sync DB) | 3 | HIGH | Enforce asyncpg/SQLAlchemy async from day 1 |
| SEC01 token auth breaks demo workflow | 4 | MEDIUM | `AUTH_DISABLED=true` env var for local dev |
| ALGO07 radar equation changes Pd system-wide | 2 | MEDIUM | Monte Carlo Pd validation before threshold changes |
| LLM structured output for XAI unreliable | 3 | MEDIUM | Pydantic output parser with fallback to plain string |
| H3 grid (LIB07) requires full zone rewrite | 5 | HIGH | Keep current zone system until H3 wrapper proven |
| RBAC breaks unauthenticated clients | 4 | HIGH | Dev mode bypass; phased rollout |

---

## Proposals Deferred or Skipped

| Proposal | Reason | Revisit When |
|----------|--------|--------------|
| ALGO06 (Bayesian belief state) | Replaces well-tested FSM; 27 tests need full rewrite; uncertain benefit | Phase 5 if research publication is a goal |
| ALGO05 (road-network patrol) | Requires road data sourcing not yet solved | After terrain module (5B) |
| ALGO09 (Raft consensus) | Premature without multi-node deployment | After multi-user auth (4E) |
| LIB10 (aiortc WebRTC feeds) | Large effort for marginal gain over MJPEG in demo context | When real hardware integration is needed |
| NEW15 (plugin system) | Requires clean subsystem boundaries | After Phase 4 architecture is stable |
| LIB07 (H3 hex grid) | Full zone model rewrite risk | Phase 5 if zone system is a bottleneck |
| LIB09 (PettingZoo RL) | Research-grade, not production-critical | Phase 5E explicitly |
| DOC02 (SAD document) | Better to write after architecture stabilizes | After Phase 2 |

---

## Success Metrics by Phase

| Metric | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|--------|---------|---------|---------|---------|---------|
| Test coverage | 80%+ | 85%+ | 85%+ | 90%+ | 90%+ |
| CRITICAL security findings | 0 | 0 | 0 | 0 | 0 |
| Autopilot dispatch success | Fixed | Tested | ROE-gated | Confidence-gated | RL-enhanced |
| Max entity scale (10Hz) | 50+50 | 100+100 | 100+100 | 100+100 | 200+200 |
| DoD 3000.09 compliance | Partial | Partial | Substantial | Full | Full |
| Operator UX gaps closed | 2 | 9 | 16 | 20+ | 25+ |
