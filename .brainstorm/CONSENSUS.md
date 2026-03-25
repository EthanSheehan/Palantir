# CONSENSUS.md — Definitive Feature Set

**Consensus Architect** | **Date:** 2026-03-20
**Synthesized from:** 20 agent analyses (Discussions 01-20), PROJECT_BRIEF, CHECKPOINT

---

## Methodology

1. Started from the Master List (Agent 16): 100 features across 10 themes
2. Applied Feasibility constraints (Agent 17): effort estimates, risk ratings, dependency chains
3. Applied Contrarian critique (Agent 18): killed over-engineered proposals, recalibrated priorities to demo/simulation scope
4. Applied Innovation rankings (Agent 19): scored all proposals on Impact x Innovation / Effort
5. Applied Wave/dependency mapping (Agent 20): ordered by prerequisite chains
6. Resolved all inter-agent conflicts (documented below)

### Scope Calibration (from Contrarian — Agent 18)

Palantir is a **demo/simulation system** showcasing AI-assisted C2 concepts, a research testbed, and a portfolio project. It is NOT a production military platform. All proposals are calibrated to this scope. Enterprise infrastructure (Kafka, Kubernetes, TimescaleDB, DISA STIGs, DO-178C, HSMs, SIEM) has been removed. The goal is: **a polished, bug-free, visually compelling demo that runs in 30 seconds from `./palantir.sh`**.

---

## Conflict Resolutions

### CR-1: PostgreSQL/TimescaleDB vs. SQLite vs. JSONL
- **Agents 05, 10, 15** recommended PostgreSQL/TimescaleDB as CRITICAL
- **Agent 18** called this absurd for a single-process demo
- **Resolution:** SQLite for persistence if needed; JSONL audit log endpoint as first step. PostgreSQL deferred to Wave 5+ only if multi-user deployment becomes real. TimescaleDB KILLED.

### CR-2: FilterPy Kalman vs. Stone Soup vs. Current Fusion
- **Agent 13** recommended both FilterPy and Stone Soup
- **Agent 18** noted implementing both means refactoring fusion twice
- **Resolution:** FilterPy Kalman (Wave 3) as the upgrade path. Stone Soup evaluated in a parallel branch only — not committed to migration. Current `1-prod(1-ci)` formula is correct and well-tested; upgrade is for research credibility, not demo necessity.

### CR-3: ECS Architecture vs. Natural Module Split
- **Agent 15** recommended full ECS formalization
- **Agent 18** called this architecture astronautics for a 20-drone sim
- **Resolution:** Split sim_engine.py by natural functional seams (UAVPhysics, TargetBehavior, etc.) — NOT because of ECS theory. Performance is not the issue; readability and testability are.

### CR-4: Per-Action Autonomy Matrix vs. Fix Existing 3-Level System
- **Agent 14** recommended per-action autonomy matrix
- **Agent 18** noted swarm coordinator ignores autonomy entirely
- **Resolution:** Fix existing autonomy system first (Wave 1-2: swarm coordinator respects autonomy, autopilot uses formal AUTONOMOUS mode). THEN add per-action granularity (Wave 4).

### CR-5: smolagents Local LLM vs. Heuristic Fallback
- **Agent 13** recommended smolagents for air-gapped operation
- **Agent 18** noted heuristic fallback already handles this
- **Resolution:** KILLED. The heuristic fallback IS the air-gapped mode. Document it as such.

### CR-6: NVIS Night Mode — Demo Value?
- **Agent 14** recommended MIL-STD-3009 NVIS mode
- **Agent 18** called this irrelevant for a web demo
- **Resolution:** DOWNGRADED to Wave 6 cosmetic. A CSS theme toggle is trivial but not priority. Included as a low-effort polish item, not a capability requirement.

### CR-7: CoT/ATAK Integration — Aspirational Scope Creep?
- **Agents 13, 14, 15** all recommended CoT bridge
- **Agent 18** noted no Android TAK devices exist in the demo environment
- **Resolution:** DEFERRED to Wave 6. Valid for positioning toward field exercises but not for current demo scope. Only if the system is demonstrably stable first.

### CR-8: Docker vs. `./palantir.sh`
- **Agents 05, 09, 13** recommended Docker as urgent
- **Agent 18** noted `./palantir.sh` already works fine
- **Resolution:** Docker Compose included in Wave 2 as a nice-to-have for reproducible deployment, NOT as urgent infrastructure. Kubernetes/Helm/Pulumi KILLED.

### CR-9: Bayesian Belief State vs. Improved Thresholds
- **Agent 02** recommended Bayesian belief state for verification
- **Agents 17, 18** both flagged this as HIGH risk — replaces clean FSM, breaks 27 tests
- **Resolution:** DEFERRED to Wave 6 (research-grade). Improve verification thresholds within the existing FSM instead. The current DETECTED to CLASSIFIED to VERIFIED pipeline is well-tested and correct.

### CR-10: Pipeline.py — Delete or Revive?
- **Agent 18** noted F2T2EAPipeline is dead code with blocking input()
- No agent recommended a concrete resolution
- **Resolution:** Delete pipeline.py or gut to a stub with docstring pointing to api_main.py. Included in Wave 1 bug fixes.

### CR-11: SampledPositionProperty Memory Leak Priority
- **Agent 07** listed as "Medium Impact" in performance doc
- **Agent 18** argued this is P0 for demo reliability (freezes after 10 min)
- **Resolution:** UPGRADED to P0. The 10-line pruning fix has massive demo reliability impact. Included in Wave 1.

### CR-12: Redis/Valkey for State Persistence
- **Agents 05, 13** recommended Redis as HIGH priority
- **Agent 18** noted single-process, localhost, no scaling requirement
- **Resolution:** KILLED for current scope. Revisit only if multi-process deployment becomes actual requirement.

### CR-13: CI/CD Pipeline Priority
- **Agents 06, 09** recommended CI as urgent (P0)
- **Agent 18** noted single-developer project where `pytest` runs locally
- **Resolution:** INCLUDED in Wave 1 as foundational tooling, but calibrated — a simple GitHub Actions workflow, not a full DevSecOps pipeline. Pre-commit hooks are higher value for a solo developer.

---

## KILLED Proposals (Removed from Backlog)

These do not belong in the backlog for a simulation/demo system:

| Proposal | Source | Reason |
|----------|--------|--------|
| PostgreSQL / TimescaleDB | 05, 10 | SQLite covers actual use case; TimescaleDB is industrial-scale |
| Redis / Valkey | 05, 13 | Single process, localhost, no scaling requirement |
| Apache Kafka | 13 | Enterprise event streaming for a 1-user demo |
| Kubernetes / Helm / Pulumi | 05, 09, 13 | Cloud orchestration for a `./palantir.sh` system |
| DO-178C compliance | 15 | FAA aviation safety certification for simulation software |
| DISA STIG hardening | 15 | DoD production hardening for a dev demo |
| HSM key storage | 15 | Hardware security modules for API keys on a laptop |
| SIEM integration | 15 | Enterprise security monitoring for a single-user system |
| MFA with hardware tokens | 15 | Multi-factor auth for a localhost demo |
| smolagents local LLM | 13 | Heuristic fallback already handles air-gapped mode |
| WebRTC via aiortc | 13 | MJPEG-over-WebSocket works fine for localhost demo |
| mediasoup SFU | 13 | Multi-operator video routing; demo has 1-2 operators |
| deck.gl GPU overlays | 13 | Six Cesium layer modes already exist |
| kepler.gl replay | 13 | JSONL log readable directly; no separate UI needed |
| Plotly/Dash analytics | 13 | Another server process for a demo with too many already |
| Mesa ABM framework | 13 | Enemy UAV behaviors extensible without full ABM |
| OpenDIS protocol | 13 | IEEE simulation federation for joint exercises |
| CrewAI agent rewrite | 13 | Full rewrite of 9 LangGraph agents with no clear gain |
| SBOM generation | 15 | Supply chain compliance for a demo project |
| cATO / DevSecOps pipeline | 15 | Continuous Authority to Operate for a dev demo |
| Formal verification / FMEA | 15 | Formal methods for simulation state machine |

---

## DEFINITIVE FEATURE SET

### Legend
- **Wave:** Implementation wave (1-6)
- **Effort:** S (<1 day) | M (1-3 days) | L (1-2 weeks) | XL (2+ weeks)
- **Priority:** P0 (must fix) | P1 (high impact) | P2 (important) | P3 (strategic/research)
- **Innovation Score:** from Agent 19 rankings (Impact x Innovation / Effort)
- **Agents:** which agents proposed/endorsed the feature

---

## Wave 1 — Foundation (No Dependencies, Maximum Parallelism)

All Wave 1 items are independent and can execute simultaneously.

**Estimated effort:** 5-6 person-days parallel (1-2 days wall-clock with team)

---

### W1-001: Fix SCANNING vs SEARCH Bug in Autopilot Dispatch
**ID:** F-001 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 10.00

**Description:** `_find_nearest_available_uav()` at `api_main.py:275` filters on `"SCANNING"` (invalid mode) instead of `"SEARCH"`. The entire autonomous target acquisition loop silently fails to assign drones. Single highest-severity single-line bug in the codebase.

**Acceptance Criteria:**
- [ ] `"SCANNING"` changed to `"SEARCH"` in `_find_nearest_available_uav()`
- [ ] `"SCANNING"` changed to `"SEARCH"` in `video_simulator.py:198`
- [ ] Demo autopilot successfully dispatches SEARCH-mode drones to new targets
- [ ] At least 3 unit tests covering the fix

**Agents:** 01 (Archaeology), 02 (Algorithms), 07 (Performance), 18 (Contrarian), 19 (Rankings) — unanimous highest priority

---

### W1-002: Fix Dead Enemy Cleanup Branch (Memory Leak)
**ID:** F-002 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 4.00

**Description:** `elif e.mode == "DESTROYED"` at `api_main.py:323` is unreachable due to a `continue` guard on line 307. `enemy_intercept_dispatched` grows without bound, leaking memory and preventing re-interception of spawned enemies with reused IDs.

**Acceptance Criteria:**
- [ ] DESTROYED enemy cleanup logic is reachable
- [ ] `enemy_intercept_dispatched` is pruned when enemies are destroyed
- [ ] Unit test verifying set is bounded after enemy destruction

**Agents:** 01 (Archaeology), 03 (Architecture)

---

### W1-003: Implement Three NotImplementedError Agents
**ID:** F-003 | **Priority:** P0 | **Effort:** M | **Innovation Score:** 5.00

**Description:** `battlespace_manager.py`, `pattern_analyzer.py`, and `synthesis_query_agent.py` all raise NotImplementedError. Clicking SITREP crashes the backend. These are dead buttons in the UI.

**Acceptance Criteria:**
- [ ] `synthesis_query_agent.generate_sitrep()` queries `sim.get_state()` and formats a SITREP
- [ ] `pattern_analyzer.analyze_patterns()` calls existing battlespace assessment functions
- [ ] `battlespace_manager.generate_mission_path()` integrates with mission_data modules
- [ ] Each agent has at least 3 unit tests
- [ ] No NotImplementedError in any agent's `_generate_response()`

**Agents:** 01 (Archaeology), 18 (Contrarian)

---

### W1-004: Fix Silent ValueError Swallowing in Autopilot
**ID:** F-005 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 4.00

**Description:** `except ValueError: pass` at api_main.py:427,498,502,507 silently swallows COA authorization failures. The autopilot silently skips failed COAs with no log entry.

**Acceptance Criteria:**
- [ ] All `except ValueError: pass` replaced with `logger.exception()` + appropriate fallback
- [ ] Failed COA authorization is visible in logs and Intel Feed
- [ ] Unit test verifying error is logged on ValueError

**Agents:** 01 (Archaeology), 03 (Architecture)

---

### W1-005: Delete or Gut pipeline.py Dead Code
**ID:** F-004 | **Priority:** P1 | **Effort:** S | **Innovation Score:** N/A

**Description:** `pipeline.py` contains a full F2T2EA pipeline class with blocking `input()` in `hitl_approve()`. It is never called in the WebSocket flow. 124 lines of dead code creating confusion about where the real pipeline runs.

**Acceptance Criteria:**
- [ ] `pipeline.py` either deleted or gutted to a stub with docstring pointing to `api_main.py`
- [ ] `test_data_synthesizer.py` (references non-existent `/ingest` endpoint) cleaned up

**Agents:** 01 (Archaeology), 03 (Architecture), 18 (Contrarian)

---

### W1-006: Fix SampledPositionProperty Frontend Memory Leak
**ID:** F-082 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 4.00

**Description:** SampledPositionProperty samples accumulate at 10Hz per drone with no pruning. After 10 minutes: 120,000+ samples, Cesium globe starts lagging. Demo freezes in front of an audience.

**Acceptance Criteria:**
- [ ] Rolling window pruner: keep only last 60 seconds of samples per drone (600 samples)
- [ ] Tether CallbackProperty replaced with pre-computed geometry update at 10Hz (not 60fps)
- [ ] Demo runs for 30+ minutes without Cesium performance degradation

**Agents:** 07 (Performance), 18 (Contrarian) — upgraded to P0 by contrarian analysis

---

### W1-007: Fix Unbounded Memory Growth in TacticalAssistant
**ID:** F-015 (partial) | **Priority:** P0 | **Effort:** S | **Innovation Score:** N/A

**Description:** `TacticalAssistant._nominated` set grows with all-time targets, never pruned. `_prev_target_states` dict never cleaned. Both cause unbounded memory growth during long demo sessions.

**Acceptance Criteria:**
- [ ] `_nominated` pruned when targets are DESTROYED or timed out
- [ ] `_prev_target_states` pruned for targets no longer in sim
- [ ] Memory stable after 30 minutes of continuous operation

**Agents:** 07 (Performance), 18 (Contrarian)

---

### W1-008: Cache get_state() Once Per Tick
**ID:** F-079 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 8.00

**Description:** `get_state()` called 2-3 times per tick, each iterating all UAVs and targets with O(U*T) `_compute_fov_targets()`. Caching eliminates 50-66% of the most expensive per-tick computation.

**Acceptance Criteria:**
- [ ] `state = sim.get_state()` computed once at top of `simulation_loop()`
- [ ] Cached value passed to broadcast, assessment, and ISR queue
- [ ] No redundant `get_state()` calls per tick

**Agents:** 07 (Performance), 19 (Rankings)

---

### W1-009: Replace O(N) Entity Lookups with Dict
**ID:** F-080 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 8.00

**Description:** `_find_uav()`, `_find_target()`, `_find_enemy_uav()` do O(N) linear scans, called 20+ times per tick. Replace with O(1) dict lookups.

**Acceptance Criteria:**
- [ ] `self.drones` / `self.targets` / `self.enemy_uavs` stored as dicts keyed by ID
- [ ] All iteration patterns use `.values()`
- [ ] All 475 existing tests pass

**Agents:** 07 (Performance), 19 (Rankings)

---

### W1-010: Move build_isr_queue() to Assessment Thread + Fix Event Logger
**ID:** F-084 | **Priority:** P1 | **Effort:** S | **Innovation Score:** 3.00

**Description:** `build_isr_queue()` runs synchronously on event loop every 5s, blocking WebSocket. Event logger opens file on every write.

**Acceptance Criteria:**
- [ ] `build_isr_queue()` moved into `asyncio.to_thread()` assessment worker
- [ ] Event logger keeps file handle open, flushes periodically
- [ ] No synchronous blocking on event loop for ISR or logging

**Agents:** 07 (Performance)

---

### W1-011: WebSocket Message Size Guard
**ID:** F-052 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 5.00

**Description:** No message size limit on incoming WebSocket messages. Trivial DoS vector.

**Acceptance Criteria:**
- [ ] Messages exceeding 64KB rejected before `json.loads()`
- [ ] Structured error response sent to client
- [ ] Unit test for oversized message rejection

**Agents:** 08 (Security)

---

### W1-012: Fix HITL Replay Attack
**ID:** F-053 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 3.33

**Description:** `_transition_entry` does not check current status before transitioning. REJECTED nominations can be replayed to APPROVED.

**Acceptance Criteria:**
- [ ] `old.status == "PENDING"` check before any state transition
- [ ] Attempted transitions from non-PENDING status logged as security events
- [ ] Unit test for replay attack prevention

**Agents:** 08 (Security)

---

### W1-013: Input Validation on All WebSocket Actions
**ID:** F-054 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 5.00

**Description:** Multiple actions accept raw values without validation: coverage mode, lat/lon (NaN/Inf), theater names, feed names.

**Acceptance Criteria:**
- [ ] Coverage mode validated against allowlist
- [ ] lat/lon validated to [-90,90] and [-180,180], reject NaN/Inf
- [ ] Confidence validated to [0,1]
- [ ] Theater name validated against `list_theaters()`
- [ ] Subscribe feed names validated against known feeds
- [ ] SITREP query length limited
- [ ] All out-of-range values rejected with structured error

**Agents:** 08 (Security)

---

### W1-014: Demo Autopilot Circuit Breaker
**ID:** F-055 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 4.00

**Description:** Demo autopilot auto-approves ALL pending nominations indefinitely. No max strike count, no rate limit, no dead-man switch. Continues if all DASHBOARD clients disconnect.

**Acceptance Criteria:**
- [ ] Max N autonomous approvals per minute (configurable)
- [ ] Halt if no DASHBOARD client connected for 30+ seconds
- [ ] Per-session engagement count limit
- [ ] Circuit breaker activations logged to Intel Feed as SAFETY events

**Agents:** 08 (Security), 14 (User Needs)

---

### W1-015: pyproject.toml with Pinned Dependencies
**ID:** F-058 (partial) | **Priority:** P0 | **Effort:** S | **Innovation Score:** 3.00

**Description:** Python dependencies use loose `>=` ranges. Different versions may install on different machines.

**Acceptance Criteria:**
- [ ] `pyproject.toml` with pinned dependency versions (upper bounds)
- [ ] ruff, mypy, pytest config in pyproject.toml
- [ ] 80% coverage threshold configured
- [ ] `pip-audit` added to dev dependencies

**Agents:** 05 (Dependencies), 09 (DevEx)

---

### W1-016: Pre-commit Hooks
**ID:** D02 | **Priority:** P0 | **Effort:** S | **Innovation Score:** 3.00

**Description:** No automated code quality gates before commit.

**Acceptance Criteria:**
- [ ] `.pre-commit-config.yaml` with ruff, black, mypy, eslint
- [ ] `make lint` target in Makefile
- [ ] All hooks pass on current codebase

**Agents:** 05 (Dependencies), 09 (DevEx)

---

### W1-017: GitHub Actions CI Pipeline
**ID:** F-087 | **Priority:** P1 | **Effort:** M | **Innovation Score:** 2.00

**Description:** No CI pipeline. Commits merge without automated verification.

**Acceptance Criteria:**
- [ ] `.github/workflows/test.yml` triggers on push and PR
- [ ] Runs ruff linting, pytest with coverage, frontend ESLint
- [ ] 80% coverage threshold as blocking check
- [ ] `/health` endpoint added to api_main.py for smoke testing

**Agents:** 06 (Testing), 09 (DevEx)

---

### W1-018: Makefile with Standard Targets
**ID:** F-090 | **Priority:** P1 | **Effort:** S | **Innovation Score:** 2.00

**Description:** No shortcut commands for common development tasks.

**Acceptance Criteria:**
- [ ] `make setup`, `make run`, `make demo`, `make test`, `make lint`, `make build`
- [ ] Documented in README

**Agents:** 09 (DevEx)

---

### W1-019: Hypothesis Property-Based Tests
**ID:** F-086 | **Priority:** P1 | **Effort:** S | **Innovation Score:** 9.00

**Description:** Critical simulation invariants need exhaustive exploration that example-based tests cannot provide.

**Acceptance Criteria:**
- [ ] `hypothesis` added to requirements
- [ ] 10-15 `@given` tests across sensor_fusion, verification_engine, swarm_coordinator, isr_priority
- [ ] Invariants tested: fusion confidence in [0,1], verification no-regression, no dual drone assignment, ISR sorted descending, theater bounds containment

**Agents:** 06 (Testing), 13 (Libraries), 19 (Rankings)

---

### W1-020: Add Shapely (Backend) and turf.js (Frontend) for Geometry
**ID:** LIB01/LIB02 | **Priority:** P1 | **Effort:** S | **Innovation Score:** 6.00

**Description:** Replace hand-rolled geometry with battle-tested libraries. Shapely for backend zone math, turf.js for frontend trig (~200 lines replaced).

**Acceptance Criteria:**
- [ ] `shapely` used in battlespace_assessment.py for polygon operations
- [ ] `@turf/turf` used in Cesium hooks replacing inline trig
- [ ] All existing tests pass

**Agents:** 05 (Dependencies), 13 (Libraries)

---

### W1-021: KD-Tree Clustering (scipy.spatial)
**ID:** ALGO01 / F-026 (partial) | **Priority:** P1 | **Effort:** S | **Innovation Score:** 6.00

**Description:** Replace O(n^2) distance loop in battlespace_assessment.py with scipy.spatial.KDTree for O(n log n) clustering.

**Acceptance Criteria:**
- [ ] `scipy.spatial.KDTree` used for distance queries
- [ ] All 21 battlespace assessment tests pass
- [ ] Measurable speedup at scale

**Agents:** 02 (Algorithms), 13 (Libraries)

---

### W1-022: Fix RTB Mode with Real Return Logic
**ID:** F-006 | **Priority:** P1 | **Effort:** S | **Innovation Score:** N/A

**Description:** RTB mode has "drift slowly for now" — no actual destination logic. UAVs do not navigate to home base.

**Acceptance Criteria:**
- [ ] Each UAV has `home_position` from theater config or initial spawn
- [ ] RTB mode uses `_turn_toward()` to navigate home
- [ ] Transition to IDLE on arrival
- [ ] Unit tests for RTB navigation

**Agents:** 01 (Archaeology), 02 (Algorithms)

---

### W1-023: UX Quick Fixes (Dead Buttons, Shortcuts)
**ID:** UX04/UX08 | **Priority:** P1 | **Effort:** S | **Innovation Score:** N/A

**Description:** Dead buttons (Range, Detail with `onClick={() => {}}`), missing keyboard shortcuts for critical operations.

**Acceptance Criteria:**
- [ ] Dead buttons either hidden or display "Coming soon" tooltip
- [ ] Escape key forces MANUAL mode (safety override)
- [ ] A/R keys approve/reject focused nomination
- [ ] Keyboard shortcut help overlay (? key)

**Agents:** 04 (UX), 18 (Contrarian)

---

**Wave 1 Total: 23 features | ~6 person-days parallel**

---

## Wave 2 — Architecture Refactor (Depends on Wave 1)

**Requires:** Wave 1 bug fixes + tests as safety net
**Estimated effort:** ~8 person-days (2A + 2B + 2D parallel; 2C after 2B)

---

### W2-001: Split sim_engine.py God Module
**ID:** F-009 | **Priority:** P1 | **Effort:** L | **Innovation Score:** 0.86

**Description:** Extract from SimulationModel (1,553 lines): UAVPhysicsEngine, TargetBehaviorEngine, EnemyUAVEngine, DetectionPipeline, AutonomyController, thin SimulationOrchestrator. Split by natural functional seams (NOT ECS theory — per CR-3).

**Acceptance Criteria:**
- [ ] Each engine in its own file with own test file
- [ ] SimulationOrchestrator owns only tick() loop and coordination
- [ ] `altitude_penalty` in sensor_model.py applied (documented but unused)
- [ ] Stale VIEWING mode comment removed
- [ ] All 475 existing tests pass

**Agents:** 03 (Architecture), 15 (Best Practices) — scoped per 18 (Contrarian)

---

### W2-002: Split api_main.py God File
**ID:** F-010 | **Priority:** P1 | **Effort:** L | **Innovation Score:** 0.86

**Description:** Extract: websocket_handlers.py (command registry replacing 200-line if/elif), simulation_loop.py, autopilot.py (decoupled from WebSocket globals), tactical_assistant.py. Fix asyncio data race (F-012).

**Acceptance Criteria:**
- [ ] Command dispatch table replaces if/elif chain (F-011)
- [ ] `demo_autopilot()` accepts injected `sim`, `hitl`, `broadcast_fn` — testable with AsyncMock
- [ ] asyncio.to_thread data race fixed (snapshot before thread dispatch)
- [ ] CORS origins moved to PalantirSettings
- [ ] Demo autopilot delays configurable
- [ ] `_process_new_detection()` uses `logger.exception()` not `str(exc)`
- [ ] `broadcast()` logs client ID on removal
- [ ] All existing tests pass

**Agents:** 03 (Architecture), 06 (Testing)

---

### W2-003: Autopilot Test Suite
**ID:** F-085 (partial) | **Priority:** P0 | **Effort:** M | **Innovation Score:** 5.00

**Description:** Now that autopilot.py is decoupled (W2-002), write the full test suite for demo_autopilot(). Currently zero tests on the full autonomous kill chain.

**Acceptance Criteria:**
- [ ] `test_demo_autopilot_approves_pending_after_delay`
- [ ] `test_demo_autopilot_dispatches_nearest_uav` (verifies SEARCH fix)
- [ ] `test_demo_autopilot_escalates_follow_to_paint`
- [ ] `test_demo_autopilot_generates_coas_after_paint`
- [ ] `test_demo_autopilot_authorizes_best_coa`
- [ ] `test_demo_autopilot_auto_intercepts_enemy_above_threshold`
- [ ] `test_demo_autopilot_skips_already_inflight`
- [ ] `test_full_kill_chain_auto_mode_completes` (integration test)
- [ ] `test_supervised_requires_approval`
- [ ] `test_autonomous_fleet_with_manual_override`

**Agents:** 06 (Testing), 03 (Architecture), 18 (Contrarian) — all agree this is highest-ROI testing work

---

### W2-004: Tests for handle_payload() and tactical_planner
**ID:** F-085 (partial) | **Priority:** P1 | **Effort:** M | **Innovation Score:** 5.00

**Description:** handle_payload() has 20+ action branches with ~2 tested. tactical_planner.py is 442 lines with zero tests.

**Acceptance Criteria:**
- [ ] All handle_payload() action branches covered (via FastAPI TestClient WebSocket)
- [ ] tactical_planner COA generation tested: all 8 pure functions
- [ ] Coverage for these modules >= 80%

**Agents:** 06 (Testing), 03 (Architecture)

---

### W2-005: Fix verify_target Handler Bypassing Verification Engine
**ID:** F-016 | **Priority:** P1 | **Effort:** S | **Innovation Score:** N/A

**Description:** `verify_target` WebSocket action directly mutates `target.state`, completely bypassing the verification engine state machine.

**Acceptance Criteria:**
- [ ] verify_target routes through verification_engine
- [ ] Operator override flag logged to audit trail
- [ ] Unit test verifying state machine is respected

**Agents:** 03 (Architecture)

---

### W2-006: Implement Swarm Coordinator Autonomy Awareness
**ID:** F-017 | **Priority:** P1 | **Effort:** M | **Innovation Score:** N/A

**Description:** Swarm coordinator completely ignores autonomy level — a comment reads "autonomy tier integration deferred." Prerequisite for per-action autonomy (CR-4).

**Acceptance Criteria:**
- [ ] MANUAL: swarm produces recommendations only (no auto-assign)
- [ ] SUPERVISED: proposed assignments surfaced as HITL transition requests
- [ ] AUTONOMOUS: assignments execute immediately
- [ ] Unit tests for each autonomy level behavior

**Agents:** 03 (Architecture), 14 (User Needs)

---

### W2-007: Docker Compose (Optional)
**ID:** F-088 | **Priority:** P2 | **Effort:** M | **Innovation Score:** 0.86

**Description:** Containerize for reproducible deployment on any host. NOT urgent — `./palantir.sh` works fine.

**Acceptance Criteria:**
- [ ] Dockerfile for Python backend (multi-stage)
- [ ] Dockerfile for React frontend (Node build + nginx)
- [ ] `docker-compose.yml` orchestrating backend + frontend + video_simulator
- [ ] `docker compose up` starts full stack

**Agents:** 05 (Dependencies), 09 (DevEx) — scoped per 18 (Contrarian)

---

### W2-008: Fix Autonomy Level Reset on Theater Switch
**ID:** F-018 | **Priority:** P2 | **Effort:** S | **Innovation Score:** N/A

**Description:** Theater switch recreates SimulationModel, resetting autonomy to MANUAL silently.

**Acceptance Criteria:**
- [ ] Autonomy level persisted across theater switches
- [ ] Warning shown before theater switch if non-MANUAL autonomy active

**Agents:** 03 (Architecture)

---

**Wave 2 Total: 8 features | ~8 person-days**

---

## Wave 3 — Core Capabilities (Depends on Wave 2)

**Requires:** Architecture refactor complete, autopilot testable
**Estimated effort:** ~10 person-days (3A + 3C + 3D + 3E parallel; 3B sequential)

---

### W3-001: ROE Engine — Deterministic Rule-Based Veto Layer
**ID:** F-031 | **Priority:** P0 | **Effort:** M | **Innovation Score:** 8.33

**Description:** Formal declarative ROE rules: `{target_type, zone, autonomy_level, collateral} -> {PERMITTED, DENIED, ESCALATE}`. ROE engine has unconditional veto power in AUTONOMOUS mode. LLM becomes advisory only.

**Acceptance Criteria:**
- [ ] `roe_engine.py` with `ROERule`, `ROEEngine.evaluate()`, `ROEDecision` enum
- [ ] YAML rule files in `theaters/roe/`
- [ ] Hooked into AutonomyController: blocks non-compliant autonomous actions
- [ ] Hooked into demo_autopilot(): checked before any nomination/authorization
- [ ] `strategy_analyst.py` returns advisory scores only (no longer safety-critical path)
- [ ] 30+ unit tests: all rule combinations, escalation, veto behavior
- [ ] ROEChangeLog — immutable append-only log of rule changes

**Agents:** 10 (Missing Modules), 14 (User Needs), 15 (Best Practices), 19 (Rankings)

---

### W3-002: Structured Audit Trail with REST Endpoint
**ID:** F-057 | **Priority:** P0 | **Effort:** M | **Innovation Score:** 4.00

**Description:** Every autonomous action logged with: timestamp, action_type, autonomy_level, sensor evidence, HITL status, operator identity. Append-only with SHA-256 hash chain.

**Acceptance Criteria:**
- [ ] `audit_log.py` with structured `AuditRecord` dataclass
- [ ] Every autonomous action logged with full context
- [ ] Every operator override logged with reason code
- [ ] SHA-256 hash chain per entry (tamper-evident)
- [ ] `GET /api/audit` REST endpoint with time/action/autonomy filters
- [ ] Override reason codes wired into TacticalAssistant prompt context

**Agents:** 14 (User Needs), 15 (Best Practices), 08 (Security)

---

### W3-003: Sensor Fusion Upgrade — FilterPy Kalman Tracks
**ID:** F-020 | **Priority:** P2 | **Effort:** L | **Innovation Score:** 3.57

**Description:** Replace `1-prod(1-ci)` with UKF per-target track state (position + covariance). Temporal decay, cross-sensor disagreement detection. Per CR-2: Stone Soup evaluated in parallel branch only.

**Acceptance Criteria:**
- [ ] `filterpy` UKF per-target in sensor_fusion.py
- [ ] `FusionResult` gains `position_estimate` and `position_covariance`
- [ ] Temporal decay for stale contributions
- [ ] Cross-sensor disagreement detection (flag when EO and SAR disagree)
- [ ] 13 existing tests updated + 15 new Kalman-specific tests
- [ ] Stone Soup evaluation in separate branch (not committed to migration)

**Agents:** 02 (Algorithms), 13 (Libraries), 12 (Research)

---

### W3-004: Swarm Coordinator Upgrade — Hungarian Algorithm
**ID:** F-024 | **Priority:** P2 | **Effort:** M | **Innovation Score:** 2.29

**Description:** Replace greedy O(T*gaps*U) with scipy.optimize.linear_sum_assignment for optimal UAV-to-target matching. Add automatic role promotion on drone loss.

**Acceptance Criteria:**
- [ ] Hungarian algorithm via scipy for assignment step
- [ ] Byzantine position anomaly detection: flag implausible position changes
- [ ] Automatic task promotion: reassign on drone loss without human intervention
- [ ] 13 existing tests updated + 10 new tests

**Agents:** 02 (Algorithms), 12 (Research)

---

### W3-005: Persistence Layer — SQLite
**ID:** F-032 | **Priority:** P2 | **Effort:** L | **Innovation Score:** 2.29

**Description:** SQLite for mission storage (per CR-1 — NOT PostgreSQL). Serialize state on target transitions and HITL decisions.

**Acceptance Criteria:**
- [ ] `MissionStore` with SQLite backend (development) — PostgreSQL deferred
- [ ] Store target lifecycle events, drone assignments, engagement outcomes
- [ ] `save_checkpoint` and `load_mission` WebSocket actions
- [ ] REST endpoints: `GET /api/missions`, `GET /api/missions/{id}`
- [ ] Async DB access (no blocking event loop)

**Agents:** 10 (Missing Modules), 05 (Dependencies) — scoped per 18 (Contrarian)

---

### W3-006: WebSocket Token Authentication
**ID:** F-051 | **Priority:** P1 | **Effort:** M | **Innovation Score:** 5.00

**Description:** Zero auth on any endpoint. Any host reaching port 8000 can approve lethal engagements. Per scope: simple API key in IDENTIFY, not full JWT (that is Wave 5).

**Acceptance Criteria:**
- [ ] Bearer token in IDENTIFY WebSocket message
- [ ] Separate token tiers for SIMULATOR (data ingest only) and DASHBOARD (full authority)
- [ ] Invalid tokens receive immediate disconnect
- [ ] `DEMO_TOKEN=dev` env var for local dev bypass
- [ ] Unit tests for auth flow

**Agents:** 08 (Security)

---

**Wave 3 Total: 6 features | ~10 person-days**

---

## Wave 4 — UX, XAI, and Autonomy Upgrade (Depends on Wave 3)

**Requires:** ROE engine, audit trail, architecture refactor
**Estimated effort:** ~11 person-days (4A-4D parallel; 4E after 3B)

---

### W4-001: AI Explainability Layer with "Why?" Button
**ID:** F-033 / F-063 | **Priority:** P1 | **Effort:** M | **Innovation Score:** 8.33

**Description:** Structured `DecisionExplanation`: action, source (LLM model or heuristic rule ID), top-3 factors with confidence scores, ROE rule satisfied, alternatives rejected, counterfactual threshold. "Why?" button on every HITL entry.

**Acceptance Criteria:**
- [ ] `DecisionExplanation` Pydantic model with structured fields
- [ ] TacticalAssistant uses chain-of-thought prompting (F-098)
- [ ] Every recommendation carries structured rationale
- [ ] Frontend "Why?" expandable panel on HITL entries
- [ ] Source label on every AI output: [AI: Gemini-2.0] / [AI: Anthropic] / [Heuristic: Rule N]
- [ ] Autopilot Decision Log panel in ASSESS tab

**Agents:** 10 (Missing Modules), 12 (Research), 14 (User Needs), 15 (Best Practices), 19 (Rankings)

---

### W4-002: Per-Action Autonomy Matrix with Time-Bounded Grants
**ID:** F-075 | **Priority:** P1 | **Effort:** M | **Innovation Score:** 8.33

**Description:** Replace global 3-level toggle with per-action policy. Each action type gets independent autonomy level. Time-bounded grants with auto-revert. Per CR-4: only after existing autonomy system works correctly.

**Acceptance Criteria:**
- [ ] `AutonomyPolicy` Pydantic model replacing scalar autonomy_level
- [ ] Each action (FOLLOW, PAINT, INTERCEPT, AUTHORIZE_COA, ENGAGE) has independent level
- [ ] `duration_seconds` parameter with auto-revert after timeout
- [ ] `exception_conditions` parameter (target types that trigger pause-and-ask)
- [ ] Frontend: policy editor UI in ASSETS tab with countdown timers
- [ ] Escape key forces MANUAL (hardware-brakeable override)

**Agents:** 14 (User Needs), 15 (Best Practices), 19 (Rankings)

---

### W4-003: Pre-Autonomy Briefing Screen
**ID:** F-062 | **Priority:** P1 | **Effort:** S | **Innovation Score:** 5.33

**Description:** Before AUTONOMOUS activation: modal showing what runs autonomously, what needs approval, what triggers reversion, active ROE rules. Require "I understand" acknowledgment. Currently one mis-click removes human from lethal loop.

**Acceptance Criteria:**
- [ ] Confirmation dialog before AUTONOMOUS (no more one-click activation)
- [ ] Briefing shows: autonomous actions, approval-required actions, reversion triggers, active ROE
- [ ] Explicit "I understand" acknowledgment required
- [ ] Autonomy level preserved across theater switches

**Agents:** 04 (UX), 14 (User Needs), 18 (Contrarian)

---

### W4-004: Confidence-Gated Dynamic Authority
**ID:** F-094 | **Priority:** P2 | **Effort:** L | **Innovation Score:** 3.57

**Description:** Even in AUTONOMOUS mode, escalate to operator when AI confidence below threshold, target in high-value category, or override rate exceeds 30%. Prevents automation complacency.

**Acceptance Criteria:**
- [ ] `confidence_threshold` per action type in AutonomyPolicy
- [ ] Below-threshold decisions pause and request operator input with structured explanation
- [ ] "Vigilance prompts" — periodic UI acknowledgment in AUTONOMOUS mode
- [ ] Frontend: confidence-gated actions glow amber in strike board
- [ ] Calibrated confidence scores displayed prominently

**Agents:** 12 (Research), 14 (User Needs), 19 (Rankings)

---

### W4-005: Global Alert Center + Strike Board Overlay
**ID:** F-059 / F-061 / F-067 | **Priority:** P1 | **Effort:** M | **Innovation Score:** 4.00

**Description:** Critical events visible across all tabs. TransitionToast system-wide (not ASSETS-only). Strike Board floats above scroll. Missed 10-second approval windows are a critical UX failure.

**Acceptance Criteria:**
- [ ] Global alert center overlay with priority queue
- [ ] TransitionToast visible from ALL tabs (not just ASSETS)
- [ ] Strike Board promoted to floating overlay (always visible)
- [ ] Audio alert option per alert type
- [ ] PENDING nominations have countdown timer
- [ ] ISR Queue one-click dispatch button (F-066)

**Agents:** 04 (UX), 14 (User Needs), 18 (Contrarian)

---

### W4-006: Override Capture with Reason Codes
**ID:** F-076 | **Priority:** P2 | **Effort:** M | **Innovation Score:** 5.33

**Description:** When operators reject AI recommendations, capture why. 3-option reason code: Wrong Target / Wrong Timing / Policy/ROE Violation. Feed into prompt context for within-session learning.

**Acceptance Criteria:**
- [ ] Reason code modal on reject action
- [ ] Logged with timestamp and operator identity
- [ ] Rolling AI recommendation acceptance rate displayed on ASSESS tab
- [ ] Reason codes fed into llm_adapter.py prompt context

**Agents:** 14 (User Needs), 15 (Best Practices), 19 (Rankings)

---

### W4-007: F2T2EA Kill Chain Progress Indicator
**ID:** F-060 | **Priority:** P2 | **Effort:** S | **Innovation Score:** N/A

**Description:** No persistent display of kill chain phase. The system's core workflow is entirely implicit.

**Acceptance Criteria:**
- [ ] Persistent kill chain ribbon: six phase indicators with target counts per phase
- [ ] Click phase to filter target list
- [ ] Color-coded by phase urgency

**Agents:** 04 (UX), 14 (User Needs)

---

### W4-008: After-Action Review Engine
**ID:** F-034 | **Priority:** P2 | **Effort:** L | **Innovation Score:** 1.43

**Description:** Variable-speed replay, decision timeline, AI vs. operator comparison. Requires persistence layer (W3-005).

**Acceptance Criteria:**
- [ ] `AAREngine` with variable-speed replay (1x-50x) from persisted snapshots
- [ ] Decision timeline structured by F2T2EA phase
- [ ] AI vs. operator comparison: where autopilot would have differed
- [ ] Frontend: REPLAY tab with timeline scrubber, speed selector
- [ ] Export: mission report JSON/CSV

**Agents:** 04 (UX), 10 (Missing Modules), 11 (Competitors)

---

### W4-009: WebSocket Connection Status Indicator
**ID:** F-074 | **Priority:** P2 | **Effort:** S | **Innovation Score:** N/A

**Description:** No indication of connection quality or data staleness. Operators may decide on stale data.

**Acceptance Criteria:**
- [ ] Connection status in header: green (<1s), yellow (1-5s), red (disconnected)
- [ ] Running average latency display
- [ ] Reconnection modal with retry count and last-connected timestamp

**Agents:** 04 (UX), 07 (Performance)

---

### W4-010: Command Palette (Cmd+K)
**ID:** F-064 | **Priority:** P2 | **Effort:** M | **Innovation Score:** 5.33

**Description:** Expert operators need keyboard-driven command interface. Every action currently requires tab navigation and scroll.

**Acceptance Criteria:**
- [ ] Global Cmd+K / Ctrl+K triggers fuzzy command search
- [ ] Commands: follow UAV, approve nomination, set autonomy, switch mode
- [ ] Command history (recently used)
- [ ] Execute immediately on selection

**Agents:** 04 (UX), 19 (Rankings)

---

### W4-011: Right-Click Context Menu on Globe
**ID:** F-065 | **Priority:** P2 | **Effort:** M | **Innovation Score:** N/A

**Description:** Right-clicking entities on Cesium globe does nothing. Real C2 systems provide immediate context menus.

**Acceptance Criteria:**
- [ ] Target right-click: Follow / Paint / Verify / Nominate / View Fusion
- [ ] Drone right-click: Set SEARCH / Assign to Target / View Camera / RTB
- [ ] Context menus execute WebSocket commands directly

**Agents:** 04 (UX)

---

### W4-012: Swarm Health At-a-Glance Panel
**ID:** F-070 | **Priority:** P2 | **Effort:** M | **Innovation Score:** N/A

**Description:** No fleet status view — operators must scroll 20 individual drone cards. Research shows SA loss at 17+ UAVs.

**Acceptance Criteria:**
- [ ] Compact grid/ring of drone indicators (color=mode, icon=sensor, border=fuel)
- [ ] Click indicator opens full drone card
- [ ] Heat-ring on Cesium showing swarm distribution vs. gaps

**Agents:** 04 (UX), 14 (User Needs)

---

**Wave 4 Total: 12 features | ~11 person-days**

---

## Wave 5 — Advanced Modules (Depends on Waves 3-4)

**Requires:** Architecture refactor, persistence, autonomy upgrade
**Estimated effort:** ~12 person-days (mostly parallel)

---

### W5-001: Simulation Fidelity Controls (Pause/Resume/Speed)
**ID:** F-037 | **Priority:** P2 | **Effort:** M | **Innovation Score:** N/A

**Description:** No ability to pause, step forward, or compress time. Researchers need fast-forward; exercise controllers need setup-phase skip.

**Acceptance Criteria:**
- [ ] `SimController` with pause/resume, 1x/5x/10x/50x time compression, single-step
- [ ] `sim_control` WebSocket action
- [ ] Frontend: speed selector + pause/play button (persistent UI)
- [ ] Pause allows state inspection before resume

**Agents:** 10 (Missing Modules), 14 (User Needs)

---

### W5-002: Scenario Scripting Engine
**ID:** F-035 | **Priority:** P2 | **Effort:** M | **Innovation Score:** N/A

**Description:** YAML exercise scripts with event timeline. Enables reproducible training, regression testing, DARPA-style exercises.

**Acceptance Criteria:**
- [ ] `ScenarioLoader` reads YAML with timeline of events
- [ ] `ScenarioPlayer` injects events at T+N: SpawnTarget, SetWeather, DegradeComms, TriggerEnemyUAV
- [ ] Demo mode becomes a YAML scenario (not hardcoded Python loop)
- [ ] Research "seed/replay" mode for reproducibility

**Agents:** 10 (Missing Modules), 14 (User Needs)

---

### W5-003: Weather + Electronic Warfare Engine
**ID:** F-039 / F-040 | **Priority:** P2 | **Effort:** M | **Innovation Score:** N/A

**Description:** Dynamic weather fronts + EW jamming effects. Activates existing EnvironmentConditions dataclass. Enemy JAMMING UAV type gets actual mechanical effects.

**Acceptance Criteria:**
- [ ] `WeatherEngine` with `tick()` advancing weather states
- [ ] Dynamic weather connects to sensor weighting and ISR priority
- [ ] `JammerModel` with spatial effect radius and frequency-specific attenuation
- [ ] Enemy JAMMING UAVs actually degrade sensor confidence in zone
- [ ] Scenario scripting integration: SetWeather, ActivateJammer events
- [ ] 20+ tests covering weather degradation effects on Pd

**Agents:** 10 (Missing Modules), 12 (Research)

---

### W5-004: Logistics Module (Fuel, Ammo, Maintenance)
**ID:** F-036 | **Priority:** P2 | **Effort:** M | **Innovation Score:** N/A

**Description:** No resource constraints. Drones never run out of fuel or ammo. Swarm coordinator cannot make real triage decisions.

**Acceptance Criteria:**
- [ ] `UAVLogistics`: fuel depletes by mode/speed, ammo decrements on engagement
- [ ] Fuel threshold triggers RTB (uses real RTB from W1-022)
- [ ] Swarm coordinator filters assignments by fuel threshold
- [ ] Frontend: fuel gauge per drone card + low-fuel system-wide alert
- [ ] YAML theater config: `base_location` for RTB destination

**Agents:** 10 (Missing Modules), 04 (UX)

---

### W5-005: Terrain Analysis Module
**ID:** F-038 | **Priority:** P3 | **Effort:** L | **Innovation Score:** 1.43

**Description:** All detection ignores terrain — UAVs detect through mountains. Major fidelity gap.

**Acceptance Criteria:**
- [ ] `TerrainModel` with DEM data per theater
- [ ] `los(observer, target)` for line-of-sight
- [ ] `DeadZoneMap` pre-computes sensor shadow zones
- [ ] Integrated with sensor_model.py: block detections with no LOS
- [ ] Cesium TERRAIN map mode shows coverage shadows

**Agents:** 10 (Missing Modules), 11 (Competitors)

---

### W5-006: Multi-User RBAC + JWT Auth
**ID:** F-044 | **Priority:** P2 | **Effort:** L | **Innovation Score:** N/A

**Description:** Full role-based access control. Builds on W3-006 token auth. Roles: OBSERVER, OPERATOR, COMMANDER, ADMIN.

**Acceptance Criteria:**
- [ ] JWT-based auth: clients present token in IDENTIFY
- [ ] Roles: OBSERVER (view), OPERATOR (assign), COMMANDER (approve/authorize), ADMIN (config)
- [ ] All HITL actions log operator identity
- [ ] Frontend: login screen, role badge in header
- [ ] `AUTH_DISABLED=true` env var for dev mode

**Agents:** 08 (Security), 10 (Missing Modules), 15 (Best Practices)

---

### W5-007: LLM Prompt Injection Defense + Output Validation
**ID:** F-056 / F-099 | **Priority:** P2 | **Effort:** M | **Innovation Score:** 2.86

**Description:** Target data flows into LLM prompts without sanitization. Output is unvalidated free text.

**Acceptance Criteria:**
- [ ] Strip newlines, control characters, instruction patterns from target fields before prompt
- [ ] All LLM responses required as structured JSON with schema validation
- [ ] Cross-check AI targeting data against verified sensor fusion (hallucination detection)
- [ ] Sanitize all reflected text in frontend

**Agents:** 08 (Security), 15 (Best Practices)

---

### W5-008: Export/Reporting Module
**ID:** F-042 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** No export capability. Command log loses older events. No mission debrief generation.

**Acceptance Criteria:**
- [ ] `ReportGenerator` for: target lifecycle, engagement outcomes, AI decision audit
- [ ] Export as CSV and JSON
- [ ] "Generate Mission Report" button in ASSESS tab

**Agents:** 04 (UX), 10 (Missing Modules)

---

### W5-009: Sensor Detection Upgrade — Radar Range Equation
**ID:** F-019 | **Priority:** P2 | **Effort:** M | **Innovation Score:** N/A

**Description:** Current `1-(r/r_max)^2` proxy overestimates detection at long range. No 1/R^4 power law.

**Acceptance Criteria:**
- [ ] `SNR proportional to P_t G^2 lambda^2 sigma / R^4` model (Nathanson)
- [ ] Configurable per sensor type: transmit power, antenna gain, wavelength, target RCS
- [ ] Weather attenuation as frequency-dependent term
- [ ] 36 existing tests updated with recalibrated thresholds
- [ ] Monte Carlo Pd validation before threshold changes

**Agents:** 02 (Algorithms), 12 (Research)

---

### W5-010: Checkpoint/Restore (Simulation Snapshots)
**ID:** ARCH05 | **Priority:** P2 | **Effort:** M | **Innovation Score:** 2.29

**Description:** Save/restore full simulation state as JSON snapshots. Enables research reproducibility and scenario replay.

**Acceptance Criteria:**
- [ ] `sim.save_checkpoint()` serializes full state to JSON
- [ ] `sim.load_checkpoint(blob)` restores state
- [ ] WebSocket actions: `save_checkpoint`, `load_checkpoint`
- [ ] Golden snapshot test for `get_state()` schema stability

**Agents:** 14 (User Needs), 15 (Best Practices), 10 (Missing Modules)

---

**Wave 5 Total: 10 features | ~12 person-days**

---

## Wave 6 — Research, Interop, and Polish (Depends on Waves 4-5)

**Estimated effort:** ~14+ person-days (largely parallel, some XL)

---

### W6-001: Forward Simulation Branches for COA Evaluation
**ID:** F-095 | **Priority:** P3 | **Effort:** L | **Innovation Score:** 3.57

**Description:** Before committing to a COA, clone the sim, run N ticks forward per COA alternative, select best predicted outcome. The "decision-oriented digital twin" — Palantir's unique architectural advantage.

**Acceptance Criteria:**
- [ ] `SimulationModel.clone()` (deepcopy of current state)
- [ ] `project_forward(model, ticks)` function
- [ ] Run in asyncio.to_thread() for each COA candidate
- [ ] Select max-score projected COA
- [ ] Predicted outcome surfaced in COA rationale

**Agents:** 12 (Research), 19 (Rankings)

---

### W6-002: CoT/ATAK Integration Bridge
**ID:** F-047 | **Priority:** P3 | **Effort:** L | **Innovation Score:** 2.86

**Description:** Bidirectional CoT XML translation using PyTAK. Per CR-7: only after system is demonstrably stable. Aspirational for field exercise positioning.

**Acceptance Criteria:**
- [ ] `cot_bridge.py` translating SimulationModel state to CoT XML
- [ ] VERIFIED targets emit as CoT hostile events on port 8089
- [ ] Subscribe to incoming CoT tracks from ATAK/WinTAK
- [ ] FreeTAKServer Docker sidecar option

**Agents:** 13 (Libraries), 14 (User Needs), 15 (Best Practices)

---

### W6-003: MIL-STD-2525 Military Symbology
**ID:** F-048 | **Priority:** P3 | **Effort:** M | **Innovation Score:** 0.86

**Description:** Standard NATO military symbols instead of custom icons. milsymbol.js integration.

**Acceptance Criteria:**
- [ ] milsymbol.js rendering standard NATO symbols on Cesium
- [ ] ontology.py entity types mapped to SIDC codes
- [ ] "Military Symbols" toggle in LayerPanel

**Agents:** 11 (Competitors), 15 (Best Practices)

---

### W6-004: Hierarchical AI Architecture (Strategic + Tactical Agent)
**ID:** F-093 | **Priority:** P3 | **Effort:** L | **Innovation Score:** N/A

**Description:** Separate strategic assessment (1Hz) from tactical execution (10Hz). Maps to DARPA hierarchical autonomy framework.

**Acceptance Criteria:**
- [ ] `StrategicAgent`: battlespace assessment, COA generation, target prioritization (1Hz)
- [ ] `TacticalAgent`: drone tasking, mode assignment, execution planning (10Hz)
- [ ] Separate LangGraph state machines
- [ ] Clean interface between layers

**Agents:** 12 (Research), 15 (Best Practices)

---

### W6-005: Frontend Testing (Vitest + Playwright E2E)
**ID:** F-091 | **Priority:** P2 | **Effort:** L | **Innovation Score:** N/A

**Description:** React frontend has zero test coverage. 40 components, WebSocket integration, Cesium hooks — all untested.

**Acceptance Criteria:**
- [ ] Vitest + @testing-library/react setup
- [ ] Playwright E2E for React: WS connect, Cesium renders, drone tracks update, HITL toast works
- [ ] Frontend tests in CI
- [ ] Minimum 5 component tests + 3 E2E tests

**Agents:** 06 (Testing), 09 (DevEx), 18 (Contrarian)

---

### W6-006: WebSocket Delta Compression
**ID:** F-081 | **Priority:** P2 | **Effort:** M | **Innovation Score:** 5.33

**Description:** Full state (~5-10KB) sent every tick to every client. Delta encoding would reduce bandwidth 50-80%.

**Acceptance Criteria:**
- [ ] Track previous state per client
- [ ] Send only changed fields per tick
- [ ] MessagePack or gzip compression option
- [ ] 50%+ bandwidth reduction measured

**Agents:** 07 (Performance), 15 (Best Practices)

---

### W6-007: Vectorize Detection Loop with NumPy
**ID:** F-083 | **Priority:** P2 | **Effort:** M | **Innovation Score:** N/A

**Description:** Detection loop O(T*U*S) is the primary scaling bottleneck. Vectorize with numpy broadcast.

**Acceptance Criteria:**
- [ ] Target/UAV positions as numpy arrays
- [ ] Pairwise distances via numpy.linalg.norm broadcast
- [ ] Detection model as element-wise array operations
- [ ] Benchmark showing 10-50x speedup at large scale

**Agents:** 07 (Performance)

---

### W6-008: Communication Simulation Module
**ID:** F-041 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** System assumes perfect zero-latency comms. No testing of graceful degradation.

**Acceptance Criteria:**
- [ ] `CommsLink` per drone: configurable latency, packet loss, bandwidth
- [ ] Presets: FULL / CONTESTED / DENIED / RECONNECT
- [ ] Autopilot handles DENIED comms with failsafe behavior

**Agents:** 10 (Missing Modules), 14 (User Needs)

---

### W6-009: Mission Planning Interface
**ID:** F-043 | **Priority:** P3 | **Effort:** L | **Innovation Score:** N/A

**Description:** No pre-mission planning capability. Operators cannot define patrol routes, search zones, or UAV assignments before a mission.

**Acceptance Criteria:**
- [ ] PLAN mode on Cesium: drag-and-drop waypoints, search area polygons
- [ ] Assign UAVs to sectors, set initial autonomy per drone
- [ ] Plans saved as MissionPlan YAML, loaded via WebSocket

**Agents:** 10 (Missing Modules), 11 (Competitors), 14 (User Needs)

---

### W6-010: PettingZoo RL Training Environment
**ID:** F-050 | **Priority:** P3 | **Effort:** XL | **Innovation Score:** 1.79

**Description:** Wrap SimulationOrchestrator as PettingZoo multi-agent env. Per contrarian: this is a multi-month research project. Only if RL research is an explicit goal.

**Acceptance Criteria:**
- [ ] `PalantirSwarmEnv(ParallelEnv)` wrapper
- [ ] Observation: per-drone sensor fusion state
- [ ] Action: mode selection (FOLLOW/PAINT/INTERCEPT/SEARCH)
- [ ] Reward: target verification progress minus time
- [ ] `step()` / `reset()` interface for external training loops

**Agents:** 12 (Research), 13 (Libraries) — scope caveat from 18 (Contrarian)

---

### W6-011: MAVLink Bridge for Real Hardware
**ID:** F-046 | **Priority:** P3 | **Effort:** XL | **Innovation Score:** 1.79

**Description:** Connect to real ArduPilot/PX4 hardware. Every drone competitor uses MAVLink.

**Acceptance Criteria:**
- [ ] `MAVLinkBridge` translating WebSocket commands to MAVLink messages
- [ ] Real drone telemetry maps to SimulationModel state
- [ ] Fallback to simulation when no hardware connected

**Agents:** 11 (Competitors), 14 (User Needs)

---

### W6-012: Engagement Outcomes with CEP Model
**ID:** F-022 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** Binary hit/miss with hardcoded 70/30 split. No CEP, no warhead model.

**Acceptance Criteria:**
- [ ] Gaussian miss-distance model: sample from N(0, CEP^2)
- [ ] Lethal radius per target type and weapon type
- [ ] Damage as continuous function of miss distance

**Agents:** 02 (Algorithms)

---

### W6-013: DBSCAN Clustering with Persistent IDs
**ID:** F-026 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** Current clustering produces edge artifacts and clusters lack persistent IDs.

**Acceptance Criteria:**
- [ ] DBSCAN from scikit-learn for density-based clustering
- [ ] Persistent cluster IDs via centroid-matching between cycles
- [ ] All 21 assessment tests pass

**Agents:** 02 (Algorithms), 13 (Libraries)

---

### W6-014: Night Operations (NVIS) Mode
**ID:** F-072 | **Priority:** P3 | **Effort:** S | **Innovation Score:** N/A

**Description:** CSS theme toggle for NVIS compatibility. Per CR-6: trivial implementation, low priority.

**Acceptance Criteria:**
- [ ] N key toggles NVIS mode
- [ ] Green-dominant low-luminance CSS theme
- [ ] All white backgrounds disabled

**Agents:** 14 (User Needs) — downgraded per 18 (Contrarian)

---

### W6-015: Color-Blind Accessible Mode
**ID:** F-073 | **Priority:** P3 | **Effort:** S | **Innovation Score:** N/A

**Description:** Red/green color coding affects ~8% of men. Shape+icon redundancy needed.

**Acceptance Criteria:**
- [ ] Shape and icon redundancy alongside color coding
- [ ] "Accessibility Mode" toggle with blue/orange palette
- [ ] WCAG AA contrast ratios audited

**Agents:** 14 (User Needs)

---

### W6-016: Map Legend, Glossary, and Onboarding
**ID:** F-071 | **Priority:** P3 | **Effort:** S | **Innovation Score:** N/A

**Description:** No map legend, no glossary, no onboarding. New users see "System Dashboard" with no guidance.

**Acceptance Criteria:**
- [ ] Map legend overlay (L key) explaining all colors/icons
- [ ] Glossary panel for military terms
- [ ] Optional 5-step tooltip walkthrough for first mission

**Agents:** 04 (UX)

---

### W6-017: Batch Approve/Reject for Nominations
**ID:** F-069 | **Priority:** P3 | **Effort:** S | **Innovation Score:** N/A

**Description:** Multiple simultaneous nominations must be approved individually. Creates backlog.

**Acceptance Criteria:**
- [ ] [Approve All / Reject All / Approve by Type] toolbar on Strike Board
- [ ] Batch confirmation with summary
- [ ] Filter by target type

**Agents:** 04 (UX)

---

### W6-018: Target Kill Log and Engagement History
**ID:** F-077 | **Priority:** P3 | **Effort:** S | **Innovation Score:** N/A

**Description:** Neutralized targets fade with no persistent record. No kill log or BDA summary.

**Acceptance Criteria:**
- [ ] "Engagement History" panel in ASSESS tab
- [ ] Chronological list: target type, time, weapon, BDA confidence, outcome
- [ ] Link to AI reasoning trace per engagement

**Agents:** 04 (UX)

---

### W6-019: Task-Focus Mode
**ID:** F-078 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** All entities render simultaneously causing cognitive overload. Auto-hide irrelevant entities based on current task.

**Acceptance Criteria:**
- [ ] T key toggles task-focus mode
- [ ] Task type inferred or selected (ISR/BDA/Strike Auth/Recon)
- [ ] Irrelevant entity types auto-hidden
- [ ] Per-layer opacity sliders in LayerPanel

**Agents:** 04 (UX), 14 (User Needs)

---

### W6-020: Dynamic Sensor Weighting
**ID:** F-030 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** Sensor fusion treats all contributions as equal regardless of environment. Existing EnvironmentConditions never affects weights.

**Acceptance Criteria:**
- [ ] Per-sensor `fitness_function(weather, time_of_day, target_type)` returning weight multiplier
- [ ] Fusion weights recalculated each tick based on environment
- [ ] ISR priority prefers SAR drones when weather degrades EO/IR

**Agents:** 02 (Algorithms), 12 (Research)

---

### W6-021: Plugin/Extension System
**ID:** F-045 | **Priority:** P3 | **Effort:** L | **Innovation Score:** N/A

**Description:** New sensor/target/agent types require editing core files.

**Acceptance Criteria:**
- [ ] `SensorPlugin`, `TargetPlugin`, `AgentPlugin` base classes
- [ ] `PluginRegistry` loads from `plugins/` directory
- [ ] Plugins register without modifying core code

**Agents:** 10 (Missing Modules)

---

### W6-022: Per-Drone Lost-Link Behavior
**ID:** F-041 (partial) | **Priority:** P3 | **Effort:** M | **Innovation Score:** 1.71

**Description:** No per-drone lost-link configuration. All drones behave identically on link loss.

**Acceptance Criteria:**
- [ ] Per-drone `lost_link_behavior`: LOITER / RTB / SAFE_LAND / CONTINUE
- [ ] Configurable in DroneCard UI
- [ ] Triggers when no telemetry for N ticks

**Agents:** 14 (User Needs)

---

### W6-023: Prometheus Metrics + Observability
**ID:** F-089 (partial) | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** No performance metrics exposed. No observability into system behavior.

**Acceptance Criteria:**
- [ ] `GET /metrics` Prometheus endpoint: tick duration, client count, detection events, HITL approvals
- [ ] OpenTelemetry traces for agent pipeline spans (optional)
- [ ] Frontend latency indicator in header

**Agents:** 09 (DevEx), 07 (Performance)

---

### W6-024: TLS Support
**ID:** SEC05 | **Priority:** P3 | **Effort:** S | **Innovation Score:** N/A

**Description:** No TLS enforcement. Only matters for non-localhost deployment.

**Acceptance Criteria:**
- [ ] Uvicorn SSL config option
- [ ] Allow HTTP on localhost, enforce HTTPS otherwise
- [ ] Origin checking on WebSocket connections

**Agents:** 08 (Security)

---

### W6-025: Behavioral Cloning from Operator Sessions
**ID:** F-097 | **Priority:** P3 | **Effort:** XL | **Innovation Score:** 1.79

**Description:** Learn autopilot policy from expert operator behavior via imitation learning.

**Acceptance Criteria:**
- [ ] Log all operator actions with simulation state as training dataset
- [ ] Train behavioral cloning policy using PalantirSwarmEnv
- [ ] Deploy as alternative to heuristic swarm coordinator

**Agents:** 12 (Research)

---

### W6-026: Federated Sensor Learning
**ID:** F-100 | **Priority:** P3 | **Effort:** L | **Innovation Score:** N/A

**Description:** Drones share learned detection calibrations across swarm.

**Acceptance Criteria:**
- [ ] Per-drone local detection confidence calibration
- [ ] Calibration factors shared via swarm coordinator
- [ ] Improved accuracy in familiar theaters over time

**Agents:** 12 (Research)

---

### W6-027: 3-DOF UAV Kinematics Upgrade
**ID:** F-029 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** 2D kinematics with no wind, no collision avoidance, no altitude model.

**Acceptance Criteria:**
- [ ] 3-DOF point-mass: position, velocity, heading, altitude
- [ ] Wind vector from theater config
- [ ] Minimum-separation collision avoidance
- [ ] Proportional navigation for intercept mode

**Agents:** 02 (Algorithms), 12 (Research)

---

### W6-028: Corridor Detection Upgrade
**ID:** F-028 | **Priority:** P3 | **Effort:** S | **Innovation Score:** N/A

**Description:** Current displacement-only threshold flags patrol loops as corridors.

**Acceptance Criteria:**
- [ ] Douglas-Peucker path simplification + Hough transform for directional consistency
- [ ] Corridor attribution (targets, time range, speed)

**Agents:** 02 (Algorithms)

---

### W6-029: Zone Balancer MPC Upgrade
**ID:** F-027 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** Proportional controller oscillates and ignores threats.

**Acceptance Criteria:**
- [ ] MPC formulation optimizing over prediction horizon
- [ ] Threat-weighted zone exposure in cost function

**Agents:** 02 (Algorithms)

---

### W6-030: OpenAPI Spec for WebSocket Protocol
**ID:** DOC01 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** No formal specification of the WebSocket protocol.

**Acceptance Criteria:**
- [ ] AsyncAPI or OpenAPI spec documenting all WebSocket actions
- [ ] Protocol version field on all messages
- [ ] Published documentation

**Agents:** 14 (User Needs)

---

### W6-031: Performance Benchmarks (pytest-benchmark + Locust)
**ID:** F-092 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** No benchmarks for tick loop scaling behavior. Optimizations cannot be measured.

**Acceptance Criteria:**
- [ ] pytest-benchmark for: tick(), get_state(), fuse_detections(), assign_tasks()
- [ ] Locust WebSocket load test: 50 concurrent clients
- [ ] Benchmarks in CI with regression tracking

**Agents:** 06 (Testing), 07 (Performance), 13 (Libraries)

---

### W6-032: Bayesian Verification Belief State (Research Track)
**ID:** F-023 | **Priority:** P3 | **Effort:** L | **Innovation Score:** 2.86

**Description:** Per CR-9: DEFERRED and marked research-grade. High risk — replaces clean FSM, breaks 27 tests. Only if continuous probability is needed for research.

**Acceptance Criteria:**
- [ ] Bayesian posterior P(VERIFIED|evidence) per target
- [ ] Configurable probability cutoff replacing fixed thresholds
- [ ] All 27 existing verification tests migrated
- [ ] Feature-flagged: can revert to FSM

**Agents:** 02 (Algorithms) — risk-flagged by 17 (Feasibility), 18 (Contrarian)

---

### W6-033: SwarmRaft Consensus Fault Tolerance
**ID:** F-096 | **Priority:** P3 | **Effort:** XL | **Innovation Score:** 1.43

**Description:** Raft-consensus based swarm coordination resilient to drone failures and GNSS degradation. Per contrarian: premature without multi-node deployment.

**Acceptance Criteria:**
- [ ] Byzantine fault detection for GNSS-denied scenarios
- [ ] Automatic task reassignment on drone failure
- [ ] Position anomaly detection (velocity exceeds physics limits)

**Agents:** 12 (Research), 03 (Architecture)

---

### W6-034: Vision Simulator Fixes
**ID:** F-007 / F-008 | **Priority:** P3 | **Effort:** S | **Innovation Score:** N/A

**Description:** TrackingScenario.update_drone() is `pass` (drone never chases targets). vision_processor.py hardcodes Bristol coordinates instead of real telemetry.

**Acceptance Criteria:**
- [ ] TrackingScenario moves drone toward target each tick
- [ ] vision_processor uses real drone telemetry, not hardcoded coordinates

**Agents:** 01 (Archaeology)

---

### W6-035: GNN Data Association for ISR Observer
**ID:** F-021 | **Priority:** P3 | **Effort:** L | **Innovation Score:** N/A

**Description:** No track correlation — same target detected by 3 UAVs appears as 3 separate detections.

**Acceptance Criteria:**
- [ ] Global Nearest Neighbor matching new detections to existing tracks
- [ ] Minimum Mahalanobis distance association
- [ ] Deduplicated target counts

**Agents:** 02 (Algorithms), 13 (Libraries)

---

### W6-036: Road-Network Target Patrol
**ID:** F-025 | **Priority:** P3 | **Effort:** L | **Innovation Score:** N/A

**Description:** Shoot-and-scoot teleports targets. Random waypoints ignore roads. Per feasibility: requires road data sourcing not yet solved.

**Acceptance Criteria:**
- [ ] Theater YAML waypoint paths for patrol routes
- [ ] Shoot-and-scoot uses finite speed (no teleport)
- [ ] Feature-flagged until road data available

**Agents:** 02 (Algorithms) — risk-flagged by 17 (Feasibility)

---

### W6-037: Magic Constants into PalantirSettings
**ID:** F-014 | **Priority:** P3 | **Effort:** M | **Innovation Score:** N/A

**Description:** ~25 magic constants not configurable without editing source. Per contrarian: physics constants can stay; demo-affecting constants should move.

**Acceptance Criteria:**
- [ ] Autopilot delays, demo FAST thresholds in PalantirSettings
- [ ] Env-var overridable for test and demo configuration
- [ ] Physics constants remain as named constants in sim

**Agents:** 03 (Architecture) — scoped per 18 (Contrarian)

---

**Wave 6 Total: 37 features | ~14+ person-days**

---

## Summary Statistics

| Wave | Features | Effort | Key Deliverables |
|------|----------|--------|-----------------|
| **Wave 1** | 23 | ~6 pd | Bug fixes, security baseline, perf quick-wins, CI, tests |
| **Wave 2** | 8 | ~8 pd | God files split, autopilot testable, Docker |
| **Wave 3** | 6 | ~10 pd | ROE engine, audit trail, Kalman fusion, auth |
| **Wave 4** | 12 | ~11 pd | XAI, per-action autonomy, alert center, AAR |
| **Wave 5** | 10 | ~12 pd | Sim controls, scenarios, weather/EW, logistics, RBAC |
| **Wave 6** | 37 | ~14+ pd | Forward sim, CoT, milsym, RL, hardware bridge, polish |
| **TOTAL** | **96** | **~61 pd** | |

### Priority Distribution

| Priority | Count | Description |
|----------|-------|-------------|
| P0 | 18 | Must fix before autonomous use |
| P1 | 20 | High impact, near-term |
| P2 | 26 | Important improvements |
| P3 | 32 | Strategic/research value |

### Fast Path to Demo-Quality Autopilot (Agent 18's "10 Things That Actually Matter")

If resources are limited, this is the minimum viable path to a polished demo:

1. **Wave 1 P0 items** (W1-001 through W1-014): Fix bugs, memory leaks, security basics — **~3 days**
2. **W2-002 + W2-003**: Decouple autopilot + write tests — **~3 days**
3. **W4-003 + W4-005**: Autonomy confirmation + global alerts — **~2 days**

**Total fast path: ~8 days** to a demo that runs correctly, looks polished, and does not crash or freeze.

### Full Autopilot Fast Path (Agent 20's procurement-quality timeline)

Waves 1-4 in sequence: **~9 weeks with 2-3 parallel engineers** to a system with XAI, per-action autonomy, audit trail, ROE engine, and procurement-demonstrable capabilities.

---

## Appendix: Agent Endorsement Matrix (Key Features)

| Feature | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 17 | 18 | 19 | 20 |
|---------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| W1-001 SCANNING fix | X | X | . | . | . | . | X | . | . | . | . | . | . | . | . | X | X | X | X |
| W1-003 NotImpl agents | X | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | X | . | . |
| W1-006 SampledProp leak | . | . | . | . | . | . | X | . | . | . | . | . | . | . | . | . | X | . | . |
| W3-001 ROE Engine | . | . | . | . | . | . | . | . | . | X | . | . | . | X | X | X | . | X | X |
| W4-001 XAI Layer | . | . | . | . | . | . | . | . | . | X | . | X | . | X | X | . | . | X | X |
| W4-002 Per-Action Auton | . | . | . | . | . | . | . | . | . | . | . | . | . | X | X | . | . | X | X |
| W4-004 Confidence-Gated | . | . | . | . | . | . | . | . | . | . | . | X | . | X | . | . | . | X | X |
| W6-001 Forward Sim | . | . | . | . | . | . | . | . | . | . | . | X | . | . | . | . | . | X | . |

*X = agent proposed or endorsed the feature*
