# 17 — Feasibility Assessment

**Role:** Feasibility Engineer
**Date:** 2026-03-20
**Input:** Discussions 01–15 (archaeology, algorithms, architecture, UX, dependencies, testing, performance, security, devex, missing modules, competitors, research, libraries, user needs, best practices)

---

## Methodology

Each proposal is rated on:
- **Feasibility:** HIGH / MEDIUM / LOW — technical viability given current codebase
- **Complexity:** estimated files changed + approximate LOC delta
- **Risk:** what could go wrong
- **Prerequisites:** what must exist first
- **Parallelizable:** can it run concurrently with other work streams

Proposals are grouped into dependency chains. A critical path is identified at the end.

---

## Proposal Index

| ID | Proposal | Source | Feasibility | Complexity | Priority |
|----|----------|--------|-------------|------------|----------|
| B01 | Fix critical bugs (SCANNING/SEARCH, dead branch, blocking input) | 01 | HIGH | 3 files, ~30 LOC | P0 |
| B02 | Implement NotImplementedError agents (battlespace_manager, pattern_analyzer, synthesis_query) | 01 | HIGH | 3 files, ~150 LOC | P0 |
| B03 | Fix COA authorization silent except swallow | 01 | HIGH | 1 file, ~5 LOC | P0 |
| A01 | Cache get_state() once per tick | 07 | HIGH | 1 file, ~10 LOC | P0 |
| A02 | Replace O(N) find_uav/target with dicts | 07 | HIGH | 2 files, ~30 LOC | P0 |
| A03 | Move build_isr_queue() into assessment thread | 07 | HIGH | 1 file, ~5 LOC | P0 |
| A04 | Fix event logger — keep file handle open | 07 | HIGH | 1 file, ~15 LOC | P0 |
| S01 | Add WebSocket message size guard | 08 | HIGH | 1 file, ~5 LOC | P0 |
| S02 | Fix HITL replay — check status before transition | 08 | HIGH | 1 file, ~10 LOC | P0 |
| S03 | Input validation for lat/lon/confidence/theater/coverage_mode | 08 | HIGH | 1 file, ~60 LOC | P0 |
| T01 | Tests for demo_autopilot() | 06 | HIGH | 1 file, ~200 LOC | P0 |
| T02 | Tests for tactical_planner COA generation | 06 | HIGH | 1 file, ~150 LOC | P0 |
| T03 | Tests for handle_payload() branches | 06 | HIGH | 1 file, ~300 LOC | P0 |
| D01 | pyproject.toml with pinned deps | 05 | HIGH | 2 files, ~80 LOC | P0 |
| D02 | Pre-commit hooks (black, ruff, mypy) | 09 | HIGH | 3 files, ~100 LOC | P0 |
| D03 | GitHub Actions CI pipeline | 09 | HIGH | 2 files, ~150 LOC | P0 |
| ARCH01 | Split api_main.py into handler modules | 03 | MEDIUM | 8 files, ~800 LOC | P1 |
| ARCH02 | Split sim_engine.py into subsystem classes | 03 | MEDIUM | 7 files, ~1000 LOC | P1 |
| ARCH03 | Fix asyncio data race (to_thread reads sim while main loop writes) | 03 | MEDIUM | 2 files, ~40 LOC | P1 |
| ARCH04 | Command dispatch table (replace 200-line if/elif) | 03 | HIGH | 1 file, ~50 LOC | P1 |
| PERF01 | Vectorize detection loop with numpy | 07 | MEDIUM | 1 file, ~80 LOC | P1 |
| PERF02 | Delta-compress WebSocket state | 07 | MEDIUM | 2 files, ~150 LOC | P1 |
| PERF03 | Prune SampledPositionProperty frontend leak | 07 | HIGH | 1 file, ~20 LOC | P1 |
| SEC01 | WebSocket token auth (Bearer in IDENTIFY) | 08 | MEDIUM | 3 files, ~200 LOC | P1 |
| SEC02 | Demo autopilot circuit breaker | 08 | HIGH | 1 file, ~40 LOC | P1 |
| UX01 | Global alert center / notification overlay | 04 | MEDIUM | 3 files, ~300 LOC | P1 |
| UX02 | Floating strike board overlay | 04 | MEDIUM | 2 files, ~200 LOC | P1 |
| UX03 | Confirmation dialog before AUTONOMOUS | 04 | HIGH | 1 file, ~60 LOC | P1 |
| UX04 | Fix dead buttons (Range, Detail) | 04 | HIGH | 1 file, ~30 LOC | P1 |
| UX05 | F2T2EA phase indicator | 04 | MEDIUM | 2 files, ~200 LOC | P1 |
| UX06 | AI decision explanation panel ("why?") | 04 | MEDIUM | 4 files, ~400 LOC | P1 |
| UX07 | Pre-autonomy briefing screen | 04, 14 | HIGH | 1 file, ~100 LOC | P1 |
| UX08 | Keyboard shortcuts (A/R approve/reject, Escape=MANUAL) | 04 | HIGH | 1 file, ~60 LOC | P1 |
| TEST01 | Property-based tests with hypothesis | 06 | HIGH | 3 files, ~150 LOC | P1 |
| TEST02 | Full kill chain integration test | 06 | MEDIUM | 1 file, ~200 LOC | P1 |
| TEST03 | GitHub Actions CI with pytest + coverage | 06 | HIGH | 1 file, ~100 LOC | P1 |
| NEW01 | ROE Engine (deterministic rule-based) | 10 | MEDIUM | 4 files, ~600 LOC | P1 |
| NEW02 | Audit log REST endpoint + structured records | 10, 14 | HIGH | 2 files, ~200 LOC | P1 |
| ALGO01 | Replace O(n²) clustering with KD-tree (scipy.spatial) | 02, 13 | HIGH | 1 file, ~30 LOC | P1 |
| LIB01 | Add Shapely for backend geometry | 13 | HIGH | 3 files, ~150 LOC | P1 |
| LIB02 | Add turf.js for frontend geospatial | 13 | HIGH | 4 files, ~200 LOC | P1 |
| LIB03 | Add Hypothesis property tests | 13 | HIGH | 3 files, ~120 LOC | P1 |
| LIB04 | Add Locust WebSocket load tests | 13 | HIGH | 1 file, ~100 LOC | P1 |
| ARCH05 | Simulation checkpoint/restore (JSON snapshots) | 15 | MEDIUM | 3 files, ~300 LOC | P2 |
| ARCH06 | ECS formalization (document + thin orchestrator) | 15 | MEDIUM | 5 files, ~400 LOC | P2 |
| ALGO02 | Sensor fusion upgrade — FilterPy Kalman tracks | 02, 13 | MEDIUM | 3 files, ~400 LOC | P2 |
| ALGO03 | Swarm coordinator — Hungarian algorithm | 02 | MEDIUM | 2 files, ~200 LOC | P2 |
| ALGO04 | RTB destination logic (replace "drift slowly") | 01, 02 | HIGH | 1 file, ~80 LOC | P2 |
| ALGO05 | Target behavior — road-network patrol (replace teleport) | 02 | LOW | 2 files, ~300 LOC | P2 |
| ALGO06 | Bayesian belief state per target (verification) | 02 | LOW | 2 files, ~400 LOC | P2 |
| ALGO07 | Proper radar range equation (1/R⁴, Nathanson) | 02 | MEDIUM | 2 files, ~200 LOC | P2 |
| NEW03 | Persistence layer (SQLite/PostgreSQL) | 05, 10 | LOW | 6 files, ~800 LOC | P2 |
| NEW04 | Logistics module (fuel, ammo, maintenance) | 10 | MEDIUM | 4 files, ~500 LOC | P2 |
| NEW05 | Simulation fidelity controls (pause/resume, speed) | 10 | HIGH | 4 files, ~400 LOC | P2 |
| NEW06 | Weather/environment engine | 10 | MEDIUM | 3 files, ~400 LOC | P2 |
| NEW07 | AI explainability layer (structured trace) | 10, 12 | MEDIUM | 4 files, ~500 LOC | P2 |
| UX09 | ISR Queue one-click dispatch | 04 | HIGH | 2 files, ~100 LOC | P2 |
| UX10 | Map right-click context menu | 04 | MEDIUM | 2 files, ~200 LOC | P2 |
| UX11 | Swarm health at-a-glance panel | 04, 14 | MEDIUM | 2 files, ~300 LOC | P2 |
| UX12 | Lost-link behavior config per drone | 14 | MEDIUM | 4 files, ~300 LOC | P2 |
| UX13 | Per-action autonomy matrix | 14 | MEDIUM | 4 files, ~400 LOC | P2 |
| UX14 | Time-bounded autonomy grants | 14 | MEDIUM | 3 files, ~250 LOC | P2 |
| UX15 | Night operations display mode (NVIS) | 14 | HIGH | 2 files, ~100 LOC | P2 |
| UX16 | Override capture + reason codes | 14 | HIGH | 3 files, ~150 LOC | P2 |
| UX17 | AI recommendation acceptance rate display | 14 | HIGH | 2 files, ~100 LOC | P2 |
| UX18 | Latency indicator in UI header | 07, 14 | HIGH | 1 file, ~50 LOC | P2 |
| LIB05 | Valkey/Redis for state persistence + pub/sub | 05, 13 | LOW | 5 files, ~600 LOC | P2 |
| LIB06 | PyTAK + FreeTAKServer CoT bridge | 11, 13 | MEDIUM | 2 files, ~400 LOC | P2 |
| TEST04 | Vitest + React Testing Library setup | 06 | MEDIUM | 5 files, ~500 LOC | P2 |
| TEST05 | Playwright E2E for React frontend | 06, 13 | MEDIUM | 4 files, ~600 LOC | P2 |
| TEST06 | Monte Carlo benchmark scenarios | 06 | MEDIUM | 2 files, ~200 LOC | P2 |
| SEC03 | RBAC — per-role WebSocket action gating | 10, 15 | MEDIUM | 3 files, ~400 LOC | P2 |
| SEC04 | Prompt injection prevention for LLM agents | 08, 15 | MEDIUM | 2 files, ~100 LOC | P2 |
| SEC05 | TLS enforcement + origin checking | 08 | MEDIUM | 2 files, ~80 LOC | P2 |
| NEW08 | After-Action Review (AAR) engine + timeline | 10 | LOW | 5 files, ~800 LOC | P3 |
| NEW09 | Scenario scripting (YAML exercise injection) | 10 | MEDIUM | 4 files, ~600 LOC | P3 |
| NEW10 | Electronic Warfare (EW) module | 10 | LOW | 4 files, ~600 LOC | P3 |
| NEW11 | Communication simulation module | 10 | LOW | 3 files, ~400 LOC | P3 |
| NEW12 | Export/reporting (PDF/CSV/JSON) | 10 | MEDIUM | 3 files, ~400 LOC | P3 |
| NEW13 | Mission planning UI (drag-and-drop pre-plan) | 10 | LOW | 6 files, ~1000 LOC | P3 |
| NEW14 | Multi-user RBAC + JWT auth | 10 | LOW | 5 files, ~700 LOC | P3 |
| NEW15 | Plugin/extension system | 10 | LOW | 5 files, ~800 LOC | P3 |
| ALGO08 | Hierarchical autonomy (dynamic confidence-gated authority) | 12 | LOW | 5 files, ~600 LOC | P3 |
| ALGO09 | Raft consensus for swarm assignment | 12 | LOW | 3 files, ~500 LOC | P3 |
| ALGO10 | Forward simulation branches for COA selection | 12 | LOW | 3 files, ~500 LOC | P3 |
| LIB07 | H3-js hex grid (replace zone system) | 13 | LOW | 6 files, ~800 LOC | P3 |
| LIB08 | Stone Soup multi-target tracking | 13 | LOW | 4 files, ~600 LOC | P3 |
| LIB09 | PettingZoo RL training environment | 13 | LOW | 5 files, ~700 LOC | P3 |
| LIB10 | aiortc WebRTC drone feeds | 13 | LOW | 5 files, ~800 LOC | P3 |
| LIB11 | MAVLink bridge for real hardware | 11 | LOW | 4 files, ~700 LOC | P3 |
| LIB12 | MIL-STD-2525 / milsymbol.js symbology | 11, 15 | MEDIUM | 3 files, ~300 LOC | P3 |
| INFRA01 | Dockerfile + docker-compose | 05, 09 | HIGH | 4 files, ~200 LOC | P2 |
| INFRA02 | /health and /ready endpoints | 09 | HIGH | 1 file, ~30 LOC | P1 |
| INFRA03 | Makefile with setup/run/test/lint targets | 09 | HIGH | 1 file, ~60 LOC | P1 |
| DOC01 | OpenAPI spec for WebSocket protocol | 14 | MEDIUM | 2 files, ~200 LOC | P2 |
| DOC02 | Software Architecture Document (SAD) | 15 | MEDIUM | 2 files, ~400 LOC | P3 |

---

## Detailed Feasibility by Proposal Group

---

### Group 1: Critical Bug Fixes (B01–B03)

#### B01 — Fix SCANNING/SEARCH bug + dead branch + blocking input()
- **Feasibility:** HIGH — pinpointed lines, trivial one-line fixes
- **Complexity:** `api_main.py` (2 lines), `pipeline.py` (1 line) — ~10 LOC
- **Risk:** LOW — fixes a confirmed bug; tests already exist for autopilot dispatch that will verify
- **Prerequisites:** None
- **Parallelizable:** Yes, independent of everything
- **Notes:** `"SCANNING"` → `"SEARCH"` is the single highest-value bug fix in the codebase. The dead `enemy_intercept_dispatched` branch can be pruned in the same PR.

#### B02 — Implement NotImplementedError in 3 agents
- **Feasibility:** HIGH — the LLM fallback chain in `llm_adapter.py` already provides a pattern to follow; the agents need their `_generate_response()` wired to actual behavior
- **Complexity:** `battlespace_manager.py`, `pattern_analyzer.py`, `synthesis_query_agent.py` — ~50 LOC each
- **Risk:** MEDIUM — requires understanding what each agent should actually return; risk of returning wrong structured type
- **Prerequisites:** B01 (ensures autopilot can actually reach these agents)
- **Parallelizable:** The three agents can be implemented in parallel

#### B03 — Fix silent COA authorization swallow
- **Feasibility:** HIGH — one-line change from `except ValueError: pass` to `logger.exception()`
- **Complexity:** `api_main.py` ~5 LOC
- **Risk:** Negligible
- **Prerequisites:** None

---

### Group 2: Performance Quick Wins (A01–A04)

#### A01 — Cache get_state() once per tick
- **Feasibility:** HIGH — straightforward; cache result at top of simulation_loop, pass cached value to downstream callers
- **Complexity:** `api_main.py` ~15 LOC
- **Risk:** LOW — risk only if some caller mutates the returned dict (they don't)
- **Prerequisites:** None
- **Parallelizable:** Yes

#### A02 — Replace linear find_uav/target with dicts
- **Feasibility:** HIGH — `SimulationModel` already has `self.uavs` and `self.targets` as lists; converting to dicts keyed by ID is mechanical
- **Complexity:** `sim_engine.py` ~40 LOC (refactor 4 methods), `api_main.py` ~10 LOC
- **Risk:** LOW — risk only if external code iterates the list expecting order (assessment loop does; must use `.values()`)
- **Prerequisites:** None
- **Parallelizable:** Yes, but conflicts with ARCH02 (sim_engine split) — do first

#### A03 — Move build_isr_queue() into assessment thread
- **Feasibility:** HIGH — 3-line change; move one function call inside the `asyncio.to_thread()` wrapper
- **Complexity:** `api_main.py` ~5 LOC
- **Risk:** LOW — assessment thread already reads sim state; adding ISR queue build is the same pattern
- **Prerequisites:** ARCH03 (data race fix) strongly recommended first
- **Parallelizable:** Can be done with ARCH03

#### A04 — Fix event logger file handle
- **Feasibility:** HIGH — refactor `EventLogger` to open file in `__init__`, flush periodically
- **Complexity:** `event_logger.py` ~20 LOC
- **Risk:** LOW — existing 15 tests will catch regressions
- **Prerequisites:** None

---

### Group 3: Security Hardening (S01–S03, SEC01–SEC05)

#### S01 — WebSocket message size guard
- **Feasibility:** HIGH — add one check before `json.loads()`
- **Complexity:** `api_main.py` ~10 LOC
- **Risk:** Negligible — configurable limit (e.g., 1 MB) won't affect normal messages
- **Prerequisites:** None

#### S02 — Fix HITL replay attack
- **Feasibility:** HIGH — add `if nomination.status != "PENDING": return` guard in `hitl_manager.py`
- **Complexity:** `hitl_manager.py` ~10 LOC
- **Risk:** Negligible — existing 14 HITL tests will validate
- **Prerequisites:** None

#### S03 — Input validation for all WebSocket actions
- **Feasibility:** HIGH — use Pydantic models already in the project to validate incoming payloads
- **Complexity:** `api_main.py` ~100 LOC (create 6-8 Pydantic request models)
- **Risk:** LOW — risk of over-restrictive validation breaking demo mode; test each action type
- **Prerequisites:** None
- **Parallelizable:** Yes

#### SEC01 — Bearer token auth on WebSocket IDENTIFY
- **Feasibility:** MEDIUM — adds auth state to connection manager; requires generating + distributing tokens outside the system (no user DB yet)
- **Complexity:** `api_main.py` ~100 LOC, new `auth.py` ~100 LOC
- **Risk:** MEDIUM — if token system is naive (static env var), it's low security; real security requires NEW14 (RBAC/JWT)
- **Prerequisites:** S03 (input validation)
- **Parallelizable:** Can run parallel to other security work

#### SEC02 — Demo autopilot circuit breaker
- **Feasibility:** HIGH — add a counter and max-strikes limit; halt if no DASHBOARD clients
- **Complexity:** `api_main.py` ~40 LOC
- **Risk:** LOW
- **Prerequisites:** B01

#### SEC03 — RBAC per-role action gating
- **Feasibility:** MEDIUM — requires user identity to flow through WebSocket connection state
- **Complexity:** `api_main.py` ~150 LOC, new `rbac.py` ~250 LOC
- **Risk:** MEDIUM — pervasive change touching every action handler
- **Prerequisites:** SEC01 (auth tokens)
- **Parallelizable:** After SEC01

#### SEC04 — Prompt injection prevention
- **Feasibility:** MEDIUM — filter known injection patterns in input before sending to LLM; use structured JSON output format
- **Complexity:** `llm_adapter.py` ~60 LOC, each agent ~10 LOC
- **Risk:** LOW — won't break heuristic fallback; LLM path already optional
- **Prerequisites:** B02 (agents must be implemented first)

#### SEC05 — TLS enforcement + origin checking
- **Feasibility:** MEDIUM — depends on deployment environment (self-signed cert complexity)
- **Complexity:** `api_main.py` ~40 LOC, deployment config ~40 LOC
- **Risk:** MEDIUM — breaks local dev if not handled gracefully (allow HTTP on localhost)
- **Prerequisites:** INFRA01 (Docker)

---

### Group 4: Architecture Refactors (ARCH01–ARCH06)

#### ARCH01 — Split api_main.py (1,113 lines → modules)
- **Feasibility:** MEDIUM — mechanical extraction but high blast radius; every file that imports `api_main` may break
- **Complexity:** Creates ~6 new files (`ws_handlers.py`, `sim_loop.py`, `autopilot.py`, `rest_endpoints.py`, `assistant.py`, `connection_manager.py`); ~800 LOC moved, ~100 LOC new glue; total ~1,113 LOC reshuffled
- **Risk:** HIGH — any integration test or import that references the old module structure breaks; careful re-export needed
- **Prerequisites:** T01, T03 (tests for autopilot and handlers must exist first — these are the safety net for refactoring)
- **Parallelizable:** Conflicts with most other api_main.py changes; do as its own phase

#### ARCH02 — Split sim_engine.py (1,553 lines → subsystems)
- **Feasibility:** MEDIUM — `SimulationModel` does too much; extracting subsystems requires careful interface design
- **Complexity:** Creates ~5 new files (`uav_physics.py`, `target_behavior.py`, `enemy_uav_engine.py`, `detection_pipeline.py`, `autonomy_controller.py`); ~1,500 LOC reshuffled
- **Risk:** HIGH — 67+ tests in `test_drone_modes.py` are tightly coupled to `SimulationModel`; refactor breaks them unless interface is preserved
- **Prerequisites:** A02 (dict lookup); TEST02 (full kill chain test as safety net); the existing 475 tests must all pass before starting
- **Parallelizable:** Conflicts with ARCH01 and ALGO series; do in a separate phase

#### ARCH03 — Fix asyncio data race
- **Feasibility:** MEDIUM — add a `threading.Lock` or switch assessment to use a snapshot copy of sim state
- **Complexity:** `api_main.py` ~30 LOC, `sim_engine.py` ~10 LOC (add snapshot method)
- **Risk:** MEDIUM — incorrect lock placement can cause deadlock; snapshot approach is safer but requires `get_state()` to be idempotent (it already is)
- **Prerequisites:** A01 (ensures get_state() is only called once, reducing lock contention)
- **Parallelizable:** Can run parallel to A01

#### ARCH04 — Command dispatch table
- **Feasibility:** HIGH — replace 200-line if/elif with a dict of `action → handler_func`; each handler is already implicitly separate
- **Complexity:** `api_main.py` ~50 LOC net change (refactor, not addition)
- **Risk:** LOW — purely structural; all existing handler logic preserved
- **Prerequisites:** None — but do before ARCH01 to reduce conflicts

---

### Group 5: New Module — ROE Engine (NEW01)

#### NEW01 — ROE Engine
- **Feasibility:** MEDIUM — deterministic rule evaluation is straightforward; the challenge is defining the rule schema and integrating with strategy_analyst + hitl_manager
- **Complexity:** `roe_engine.py` ~300 LOC, `roe_rules.yaml` ~100 LOC, integration in `pipeline.py` + `strategy_analyst.py` ~200 LOC; total ~600 LOC
- **Risk:** MEDIUM — if ROE engine has veto power in AUTONOMOUS mode, a misconfigured rule blocks all autonomous engagements; needs careful default rules
- **Prerequisites:** B01, B02; NEW01 depends on agents being functional
- **Parallelizable:** Can be built in parallel with UX work

---

### Group 6: UX Improvements (UX01–UX18)

#### UX03 — Confirmation before AUTONOMOUS (highest safety value)
- **Feasibility:** HIGH — a Dialog component with "I understand" acknowledgment; Blueprint Dialog already used in the codebase
- **Complexity:** 1 component ~60 LOC
- **Risk:** LOW
- **Prerequisites:** None
- **Parallelizable:** Yes

#### UX07 — Pre-autonomy briefing screen
- **Feasibility:** HIGH — a static modal displaying current ROE state, what actions will auto-approve, reversion triggers
- **Complexity:** 1 component ~100 LOC
- **Risk:** LOW
- **Prerequisites:** NEW01 (ROE engine provides content) or can be hardcoded initially
- **Parallelizable:** Yes

#### UX06 — AI decision explanation panel
- **Feasibility:** MEDIUM — requires the backend to attach structured reasoning trace to every AI action; frontend renders it
- **Complexity:** `TacticalAssistant` +~100 LOC, new `ExplanationPanel.tsx` ~150 LOC, WebSocket protocol extension ~50 LOC, `StrikeBoardEntry` update ~100 LOC
- **Risk:** MEDIUM — structured reasoning requires LLM to output JSON consistently; heuristic path needs its own trace format
- **Prerequisites:** B02 (agents functional), NEW07 (explainability layer) or implemented together
- **Parallelizable:** Frontend can build the panel against a mock trace; backend wires it separately

#### UX01 — Global alert center
- **Feasibility:** MEDIUM — requires a persistent notification bus in Zustand that all tabs can read
- **Complexity:** `SimulationStore.ts` +~80 LOC, new `AlertCenter.tsx` ~150 LOC, WebSocket event listener updates across tabs ~80 LOC
- **Risk:** LOW — purely additive
- **Prerequisites:** None
- **Parallelizable:** Yes

#### UX13 — Per-action autonomy matrix
- **Feasibility:** MEDIUM — extends autonomy model from 3-level global to per-action-type; requires new state in SimulationModel + WebSocket protocol change
- **Complexity:** `sim_engine.py` +~100 LOC, `api_main.py` +~100 LOC, `AutonomyPanel.tsx` +~200 LOC
- **Risk:** MEDIUM — pervasive change; every action handler must check the matrix instead of global level
- **Prerequisites:** ARCH04 (dispatch table makes per-action checks easier)
- **Parallelizable:** After ARCH04

#### UX12 — Lost-link behavior config
- **Feasibility:** MEDIUM — add per-drone `lost_link_behavior` field (LOITER/RTB/SAFE_LAND/CONTINUE); handle in sim_engine when no telemetry received for N ticks
- **Complexity:** `sim_engine.py` +~80 LOC, `api_main.py` +~40 LOC, `DroneCard.tsx` +~80 LOC
- **Risk:** LOW — additive feature; default behavior unchanged
- **Prerequisites:** ALGO04 (RTB destination logic)
- **Parallelizable:** Yes after ALGO04

---

### Group 7: Algorithm Upgrades (ALGO01–ALGO10)

#### ALGO01 — KD-tree clustering (scipy.spatial)
- **Feasibility:** HIGH — `scipy.spatial.KDTree` is a 2-line import; replaces O(n²) loop
- **Complexity:** `battlespace_assessment.py` ~30 LOC
- **Risk:** LOW — existing 21 battlespace tests validate output
- **Prerequisites:** None
- **Parallelizable:** Yes

#### ALGO04 — RTB destination logic
- **Feasibility:** HIGH — replace "drift slowly" with actual home-base coordinates from theater YAML
- **Complexity:** `sim_engine.py` ~50 LOC, `theaters/*.yaml` ~20 LOC each
- **Risk:** LOW — clear improvement; existing tests don't cover RTB so won't break
- **Prerequisites:** None
- **Parallelizable:** Yes

#### ALGO02 — Kalman track fusion (FilterPy)
- **Feasibility:** MEDIUM — UKF requires per-target state (position + velocity covariance matrix); existing `sensor_fusion.py` is stateless; this adds statefulness
- **Complexity:** `sensor_fusion.py` +~200 LOC (new `TrackFusion` class with per-target KF state), `sensor_fusion.py` tests +~100 LOC
- **Risk:** MEDIUM — changes the `FusionResult` dataclass (adds covariance field); any code reading `fusion_confidence` directly still works; anything checking for exact FusionResult structure breaks
- **Prerequisites:** ALGO01 (fast clustering first)
- **Parallelizable:** Can run parallel to most other work

#### ALGO03 — Hungarian algorithm for swarm assignment
- **Feasibility:** MEDIUM — `scipy.optimize.linear_sum_assignment` already available; the challenge is formulating the cost matrix correctly with sensor-gap detection
- **Complexity:** `swarm_coordinator.py` ~100 LOC (replace greedy loop), tests +~80 LOC
- **Risk:** LOW — existing 13 swarm tests validate assignment correctness; algorithm is well-tested in scipy
- **Prerequisites:** ALGO01 (faster lookups reduce cost matrix build time)
- **Parallelizable:** Yes

#### ALGO05 — Road-network target patrol
- **Feasibility:** LOW — requires a road network graph (not in theaters/*.yaml); either embed simplified waypoint graphs in YAML or pull from OpenStreetMap (requires network call)
- **Complexity:** `sim_engine.py` +~200 LOC, `theaters/*.yaml` +~100 LOC per theater
- **Risk:** HIGH — without real road data, simulated patrols look artificial; mismatches terrain
- **Prerequisites:** NEW06 (terrain/environment); road data sourcing is unsolved
- **Parallelizable:** After terrain system

#### ALGO06 — Bayesian belief state per target
- **Feasibility:** LOW — replaces the clean linear FSM (DETECTED→CLASSIFIED→VERIFIED) with a continuous probability; all downstream code that checks `target.state == "VERIFIED"` breaks
- **Complexity:** `verification_engine.py` rewrite ~400 LOC, 27 existing tests require full rewrite
- **Risk:** HIGH — the current FSM is well-tested and depended upon everywhere; Bayesian upgrade is a full replacement, not an addition
- **Prerequisites:** ALGO02 (Kalman fusion feeds Bayesian belief)
- **Parallelizable:** After ALGO02; conflicts with ARCH02

#### ALGO07 — Proper radar range equation
- **Feasibility:** MEDIUM — the Nathanson SNR model is well-documented; replacing the sigmoid proxy is ~100 LOC; the hard part is parameterizing it (transmit power, antenna gain, wavelength per sensor type)
- **Complexity:** `sensor_model.py` ~100 LOC, `theaters/*.yaml` +~30 LOC (new sensor parameters), 36 existing tests need range threshold updates
- **Risk:** MEDIUM — changes Pd values system-wide; verification thresholds (tuned for current Pd) may need recalibration
- **Prerequisites:** None, but coordinate with ALGO06 if Bayesian belief is planned
- **Parallelizable:** Yes

---

### Group 8: New Modules (NEW02–NEW15)

#### NEW02 — Audit log REST endpoint
- **Feasibility:** HIGH — `event_logger.py` already writes JSONL; add a `GET /api/audit` endpoint that reads and returns it with filtering
- **Complexity:** `api_main.py` +~80 LOC, `event_logger.py` +~40 LOC (structured audit record)
- **Risk:** LOW
- **Prerequisites:** A04 (fix event logger file handle first)
- **Parallelizable:** Yes

#### NEW05 — Simulation fidelity controls (pause/resume/speed)
- **Feasibility:** HIGH — add a `SimController` with `paused: bool` and `speed_factor: float` checked at top of each tick; WebSocket action `sim_control`
- **Complexity:** `sim_engine.py` +~60 LOC, `api_main.py` +~80 LOC, `SimControlPanel.tsx` +~150 LOC
- **Risk:** LOW — pause is trivially safe; speed_factor > 1× may stress the 100ms budget at high entity counts
- **Prerequisites:** None
- **Parallelizable:** Yes

#### NEW04 — Logistics module (fuel/ammo/maintenance)
- **Feasibility:** MEDIUM — fuel can be added as a field on UAV objects; ammo decrements on engagement; RTB trigger when fuel < threshold
- **Complexity:** `sim_engine.py` +~150 LOC (new UAVLogistics dataclass + tick integration), `swarm_coordinator.py` +~50 LOC (filter by fuel), frontend +~100 LOC (fuel gauge on DroneCard)
- **Risk:** LOW — additive; existing behavior unchanged until fuel reaches threshold
- **Prerequisites:** ALGO04 (RTB logic must exist for fuel-triggered RTB)
- **Parallelizable:** Yes after ALGO04

#### NEW03 — Persistence layer (SQLite/PostgreSQL)
- **Feasibility:** LOW — the codebase uses no ORM and has no DB schema; adding SQLAlchemy + migrations is a significant infrastructure lift
- **Complexity:** New `persistence/` package ~400 LOC, `alembic/` migrations ~200 LOC, refactored `hitl_manager.py` and `event_logger.py` ~200 LOC
- **Risk:** HIGH — migrations, connection pool management, async DB access (must use asyncpg or SQLAlchemy async); risk of blocking the event loop if sync DB calls are used
- **Prerequisites:** ARCH01 (api_main.py split to isolate persistence logic), LIB05 optional (Redis alternative for lighter persistence)
- **Parallelizable:** Can be built in isolation; integration is the risky step

#### NEW06 — Weather/environment engine
- **Feasibility:** MEDIUM — `EnvironmentConditions` dataclass already exists in the codebase but is at static defaults; activating it requires connecting it to the tick loop and the sensor model
- **Complexity:** `weather_engine.py` ~200 LOC, `sensor_model.py` +~60 LOC (consume weather state), `sim_engine.py` +~40 LOC (tick weather), frontend weather indicator ~100 LOC
- **Risk:** LOW — existing `EnvironmentConditions` provides the interface; filling it with dynamic values is additive
- **Prerequisites:** None
- **Parallelizable:** Yes

#### NEW07 — AI explainability layer
- **Feasibility:** MEDIUM — structured reasoning trace requires agents to output JSON with `factors`, `confidence`, `alternatives_rejected` fields; prompt engineering change + response parser change
- **Complexity:** `llm_adapter.py` +~80 LOC (new structured response format), each agent +~30 LOC (parse + return trace), `explainability_store.py` ~150 LOC, frontend panel ~200 LOC
- **Risk:** MEDIUM — LLM output JSON consistency varies; needs robust fallback when trace is malformed
- **Prerequisites:** B02 (agents functional); can be wired before UX06
- **Parallelizable:** Yes, parallel to UX06 frontend work

#### NEW08 — After-Action Review (AAR) engine
- **Feasibility:** LOW — full replay requires time-indexed state snapshots at every tick (or at decision points); current JSONL only logs events, not full state
- **Complexity:** `aar_engine.py` ~300 LOC, `event_logger.py` +~100 LOC (snapshot at each state transition), `AARTab.tsx` ~400 LOC (timeline scrubber)
- **Risk:** HIGH — snapshot storage is bounded only by disk; aggressive snapshotting at 10Hz creates large files; selective snapshotting requires careful event selection
- **Prerequisites:** ARCH05 (checkpoint/restore), NEW03 (persistence) or a dedicated snapshot store
- **Parallelizable:** After ARCH05

#### NEW09 — Scenario scripting (YAML exercise injection)
- **Feasibility:** MEDIUM — inject events (SpawnTarget, SetWeather, DegradeComms) at T+N seconds; event types map to existing WebSocket actions
- **Complexity:** `scenario_player.py` ~200 LOC, `scenario_loader.py` ~100 LOC, `scenarios/*.yaml` examples ~150 LOC, `api_main.py` +~80 LOC (consume scenario events)
- **Risk:** LOW — additive; does not change existing code paths
- **Prerequisites:** NEW05 (speed controls enable fast-forward); NEW06 (weather injection); NEW11 (comms degradation injection)
- **Parallelizable:** Yes, can build loader/player before injection points are wired

#### NEW10 — Electronic Warfare (EW) module
- **Feasibility:** LOW — jamming effects require the sensor model to check an EW environment state; enemy JAMMING UAV type already exists but has no mechanical effect on sensors
- **Complexity:** `ew_module.py` ~250 LOC, `sensor_model.py` +~80 LOC (check jamming), `sensor_fusion.py` +~40 LOC (downweight jammed sensors)
- **Risk:** MEDIUM — changes Pd calculations globally; risk of breaking sensor confidence thresholds used in verification
- **Prerequisites:** ALGO07 (proper sensor model first), NEW06 (weather engine establishes environment state pattern)
- **Parallelizable:** After ALGO07

#### NEW09-NEW15 — Communication simulation, Export/Reporting, Mission Planning UI, Multi-User RBAC, Plugin System
- **Feasibility:** LOW for most — these are significant standalone features requiring dedicated subsystems
- **Risk:** HIGH for NEW14 (RBAC touches every handler), MEDIUM for others
- **Prerequisites:** NEW14 requires SEC01 (auth tokens); NEW13 requires ARCH05 (scenario save/load); NEW15 requires ARCH01+ARCH02 (clean subsystem boundaries to plug into)

---

### Group 9: Infrastructure (INFRA01–INFRA03)

#### INFRA01 — Docker + docker-compose
- **Feasibility:** HIGH — the system has clear startup commands in `grid_sentinel.sh`; containerizing FastAPI + React Vite is well-understood
- **Complexity:** `Dockerfile.backend` ~40 LOC, `Dockerfile.frontend` ~30 LOC, `docker-compose.yml` ~80 LOC, `.dockerignore` ~20 LOC
- **Risk:** LOW — native deps (opencv) require `python:3.11-slim` with build tools; documented in Dockerfile
- **Prerequisites:** D01 (pinned deps make Dockerfile reproducible)
- **Parallelizable:** Yes

#### INFRA02 — /health endpoint
- **Feasibility:** HIGH — a FastAPI route returning `{"status": "ok", "tick_count": N}`
- **Complexity:** `api_main.py` ~30 LOC
- **Risk:** None
- **Prerequisites:** None

#### INFRA03 — Makefile
- **Feasibility:** HIGH — simple phony targets wrapping existing commands
- **Complexity:** `Makefile` ~60 LOC
- **Risk:** None

---

## Dependency Chains

Dependency chains group proposals where B cannot start until A is complete (or substantially complete).

### Chain 1: Stability Foundation (must come first, mostly P0)
```
D01 (pinned deps)
  └── D02 (pre-commit hooks)
        └── D03 (CI pipeline)
              └── TEST03 (CI with coverage)

B01 (SCANNING bug + dead branch)
B03 (COA swallow fix)
S01 (message size guard)
S02 (HITL replay fix)
A04 (event logger handle)
INFRA02 (/health endpoint)
INFRA03 (Makefile)
```
All of these are independent of each other and can run fully in parallel.

### Chain 2: Test Coverage Before Refactoring
```
T01 (demo_autopilot tests)
T02 (tactical_planner tests)
T03 (handle_payload tests)
TEST01 (hypothesis property tests)
  └── ARCH01 (split api_main.py — tests are the safety net)
        └── ARCH04 (dispatch table — cleaner with split file)
              └── UX13 (per-action autonomy matrix — needs dispatch table)
                    └── UX14 (time-bounded autonomy — extends per-action matrix)
```

### Chain 3: Performance Path
```
A02 (dict lookups)
  └── A01 (cache get_state)
        └── ARCH03 (data race fix — single get_state makes this safe)
              └── A03 (ISR queue into assessment thread)
PERF03 (prune SampledPositionProperty — frontend, independent)
PERF01 (vectorize detection — after A02 since loop now uses dicts)
PERF02 (delta compression — after ARCH01 so the state builder is isolated)
```

### Chain 4: Agent Completion Chain
```
B02 (implement 3 NotImplementedError agents)
  └── SEC04 (prompt injection — agents must be functional first)
        └── NEW07 (explainability layer — agents output structured trace)
              └── UX06 (AI explanation panel — consumes trace)
                    └── UX17 (acceptance rate display — uses explanation data)
```

### Chain 5: Sensor Quality Chain
```
ALGO01 (KD-tree clustering — quick win)
  └── ALGO02 (Kalman fusion — better position estimates improve clustering)
        └── ALGO07 (radar equation — feeds better Pd into Kalman)
              └── ALGO06 (Bayesian belief — replaces FSM with continuous prob)
                        [NOTE: ALGO06 is optional/risky — may skip]
```

### Chain 6: Security Escalation Chain
```
S01 + S02 + S03 (basic hardening — P0)
  └── SEC01 (auth token on IDENTIFY)
        └── SEC03 (RBAC per role)
              └── NEW14 (full multi-user RBAC + JWT)
SEC02 (circuit breaker — independent, can go any time after B01)
SEC05 (TLS — after INFRA01/Docker)
```

### Chain 7: Autonomy Enhancement Chain
```
B01 (fix autopilot dispatch)
  └── NEW01 (ROE engine — deterministic safety layer)
        └── UX07 (pre-autonomy briefing — shows ROE state)
              └── UX13 (per-action autonomy matrix)
                    └── UX14 (time-bounded grants)
                          └── ALGO08 (hierarchical dynamic authority — research-grade)
```

### Chain 8: Persistence & AAR Chain
```
A04 (event logger fix)
  └── NEW02 (audit log REST endpoint)
        └── ARCH05 (checkpoint/restore)
              └── NEW03 (SQLite/PostgreSQL persistence)
                    └── NEW08 (AAR engine — needs state snapshots)
                          └── LIB07 (kepler.gl replay visualization)
```

### Chain 9: New Feature Modules (mostly independent, P2)
```
ALGO04 (RTB logic)
  └── UX12 (lost-link behavior)
        └── NEW04 (logistics — fuel triggers RTB)

NEW05 (pause/resume/speed)
NEW06 (weather engine)
  └── NEW10 (EW module — uses environment state pattern)
        └── NEW11 (comms simulation — same pattern)
              └── NEW09 (scenario scripting — injects weather/comms events)
                    └── NEW08 (AAR — replays scripted scenarios)
```

### Chain 10: Interoperability Chain (P2-P3)
```
LIB06 (PyTAK CoT bridge)
  └── LIB12 (MIL-STD-2525 symbology)
LIB11 (MAVLink bridge — standalone, P3)
```

### Chain 11: Simulation Refactoring Chain
```
[All tests passing]
  └── ARCH02 (split sim_engine.py)
        └── ARCH06 (ECS formalization)
              └── LIB07 (H3-js hex grid — replaces zone model)
                    └── ALGO09 (Raft consensus — needs clean swarm interface)
                          └── LIB09 (PettingZoo RL training)
```

---

## Critical Path

The critical path is the longest chain of dependent proposals that governs the minimum timeline for the full feature set.

```
D01 (pinned deps) [1 day]
  → D02 (pre-commit hooks) [1 day]
    → D03 (CI pipeline) [2 days]
      → T01 + T02 + T03 (test coverage) [3 days, parallel]
        → ARCH01 (split api_main.py) [3 days]
          → ARCH04 (dispatch table) [1 day]
            → SEC01 (WebSocket auth) [2 days]
              → SEC03 (RBAC) [3 days]
                → NEW14 (JWT auth + multi-user) [5 days]
```

**Total critical path estimate: ~21 working days** to reach full RBAC auth.

The second-longest path to core autopilot quality:

```
B01 (SCANNING fix) [0.5 day]
  → B02 (agent stubs) [2 days]
    → NEW01 (ROE engine) [5 days]
      → UX07 (pre-autonomy briefing) [1 day]
        → UX13 (per-action autonomy) [3 days]
          → UX14 (time-bounded grants) [2 days]
```

**~14 working days** to a meaningfully enhanced autopilot.

The sensor quality path:

```
ALGO01 (KD-tree) [0.5 day]
  → ALGO02 (Kalman fusion) [4 days]
    → ALGO07 (radar equation) [2 days]
      [ALGO06 optional — skip for now]
```

**~7 working days** to substantially improved sensor fidelity.

---

## Parallelization Opportunities

The following groups can run simultaneously with no conflicts:

| Wave | Workstreams (can run in parallel) |
|------|-----------------------------------|
| Wave 1 | B01, B03, S01, S02, S03, A04, INFRA02, INFRA03, D01, ALGO01, ALGO04, PERF03 |
| Wave 2 | D02+D03 (need D01), T01+T02+T03 (can start), A01+A02 (after B01), SEC02 (after B01), UX03+UX04+UX08+UX15 (pure frontend, no deps), NEW05 (sim controls), NEW06 (weather), LIB03+LIB04 (testing tools), A04→NEW02 (audit log) |
| Wave 3 | ARCH03 (data race, after A01), TEST01 (hypothesis, after T01-T03), ALGO02 (Kalman, after ALGO01), ALGO03 (Hungarian, after ALGO01), UX01+UX02+UX05+UX09+UX18 (frontend UX, mostly independent), B02 (agents), SEC01 (auth, after S03) |
| Wave 4 | ARCH01 (after T01-T03 + A02), B02→SEC04→NEW07→UX06 (agent chain), ARCH03→A03 (ISR queue move), ALGO02→ALGO07 (sensor model), NEW04 (logistics, after ALGO04), UX12 (lost-link, after ALGO04) |
| Wave 5 | ARCH04 (after ARCH01), PERF01+PERF02 (after ARCH01+A02), NEW01 (ROE, after B02), TEST02 (kill chain test), INFRA01 (Docker, after D01), LIB01+LIB02 (Shapely+turf.js), TEST04+TEST05 (frontend testing) |
| Wave 6 | SEC03 (RBAC, after SEC01), UX13+UX14 (autonomy matrix, after ARCH04+NEW01), UX06+UX07 (AI explanation, after NEW07), ARCH05 (checkpoint), NEW09 (scenario scripting), ARCH02 (sim engine split — if warranted) |
| Wave 7 | NEW03 (persistence, after ARCH01+ARCH05), NEW08 (AAR, after ARCH05), NEW10+NEW11 (EW+comms, after NEW06), LIB06 (CoT bridge), SEC05 (TLS, after INFRA01) |
| Wave 8 | NEW14 (full RBAC, after SEC03), ALGO08+ALGO09+ALGO10 (research-grade autonomy), LIB07+LIB08+LIB09 (H3/StoneSoup/RL), NEW13 (mission planning UI), LIB10+LIB11 (WebRTC/MAVLink) |

---

## Risk Register

| Risk | Severity | Proposals Affected | Mitigation |
|------|-----------|--------------------|------------|
| ARCH01/ARCH02 refactors break 475 tests | HIGH | ARCH01, ARCH02 | Enforce green tests before starting; do in isolation sprint |
| ALGO06 (Bayesian belief) invalidates all verification code | HIGH | ALGO06 + downstream | Mark as optional; default to improving thresholds instead |
| NEW03 (persistence) blocks event loop if sync DB calls used | HIGH | NEW03 | Enforce asyncpg/SQLAlchemy async from the start |
| SEC01 token auth breaks demo workflow | MEDIUM | SEC01 | Allow `DEMO_TOKEN=dev` env var to bypass in local dev |
| ALGO07 (radar equation) changes Pd → verification thresholds need recalibration | MEDIUM | ALGO07, verification | Run Monte Carlo Pd validation before changing thresholds |
| H3 grid (LIB07) requires full zone model rewrite | HIGH | LIB07 | Treat as a separate phase; keep current zone system until H3 wrapper is proven |
| LLM structured output for NEW07 unreliable | MEDIUM | NEW07, UX06 | Implement Pydantic output parser with fallback to plain string |
| ARCH02 (sim_engine split) creates circular imports | MEDIUM | ARCH02 | Design interfaces first; use dependency injection |
| NEW14 (RBAC) breaks all existing unauthenticated clients | HIGH | NEW14 | Keep dev mode (no auth) with env var `AUTH_DISABLED=true` |

---

## Recommended Execution Order (Summary)

### Phase A — P0 Stabilization (Waves 1–2, ~1 week)
Fix all critical bugs, security basics, performance quick wins, and CI infrastructure. Everything in Wave 1 + Wave 2. These are the prerequisites for all future work and can be committed as a single "stabilization" release.

**Key deliverables:** Autopilot dispatch bug fixed, HITL replay attack closed, CI pipeline live, coverage threshold enforced, event logger stable, all P0 bugs resolved.

### Phase B — Quality Foundation (Waves 3–4, ~2 weeks)
Test coverage for the untested paths (autopilot, handlers, planner). Agents implemented. Data race fixed. Kalman fusion prototype. Auth token baseline.

**Key deliverables:** 80%+ test coverage, demo_autopilot tested, agents functional, sensor fusion upgraded, WebSocket auth live.

### Phase C — Architecture & UX (Waves 4–5, ~2 weeks)
api_main.py split (with test safety net). ROE engine. Major UX gaps closed (alert center, explanation panel, autonomy confirmation, ISR one-click, NVIS mode).

**Key deliverables:** God files split, ROE engine, meaningful UX improvements for operators, Docker image available.

### Phase D — New Capabilities (Waves 5–7, ~3 weeks)
Logistics, weather, scenario scripting, persistence layer, AAR foundation, RBAC, CoT bridge.

**Key deliverables:** Fuel system, weather effects, reproducible scenarios, basic persistence, ATAK interoperability.

### Phase E — Research Grade (Wave 8, ongoing)
Hierarchical autonomy, RL training environment, Stone Soup tracking, MAVLink hardware bridge, full AAR timeline, mission planning UI, plugin system.

**Key deliverables:** Academic research platform, hardware integration path, full RBAC.

---

## Bottom-Line Judgment

**Most impactful proposals by effort/impact ratio (do first):**

1. **B01** (SCANNING fix) — 30 min work, unblocks autopilot dispatch
2. **A02** (dict lookups) — 1 hour, 10-50% speedup at scale
3. **S02** (HITL replay fix) — 30 min, closes critical security hole
4. **D01** (pinned deps + pyproject.toml) — 2 hours, enables CI
5. **T01+T02+T03** (tests for untested paths) — 2 days, safety net for all refactoring
6. **UX03** (AUTONOMOUS confirmation dialog) — 1 hour, highest safety/effort ratio
7. **SEC02** (autopilot circuit breaker) — 1 hour, prevents runaway autonomous engagement
8. **ALGO01** (KD-tree clustering) — 30 min, O(n²) → O(n log n)
9. **NEW02** (audit log REST endpoint) — 4 hours, compliance deliverable
10. **NEW05** (pause/resume sim) — 4 hours, high operator value

**Proposals to defer or skip:**
- **ALGO06** (Bayesian belief state) — too high risk for uncertain benefit; improve verification thresholds instead
- **ALGO05** (road-network patrol) — requires road data sourcing not yet solved
- **NEW03** (PostgreSQL) — high complexity; Redis/Valkey is sufficient for near-term state persistence
- **LIB10** (aiortc WebRTC) — large effort for marginal gain over current MJPEG in demo context
- **ALGO09** (Raft consensus) — premature without multi-node deployment
- **NEW14** (full RBAC) — valid long-term goal; SEC01+SEC03 cover 90% of the safety value at 20% of the cost
