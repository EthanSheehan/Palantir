# Wave 1 Refined Consensus — Builder Spec

**Date:** 2026-03-20
**Source:** `.brainstorm/CONSENSUS.md` (96 features, 6 waves), `.brainstorm/ROADMAP.md`
**Scope:** 23 Wave 1 features only — Foundation & Critical Fixes
**Estimated effort:** 5-6 person-days parallel (~1-2 days wall-clock with team)

---

## 1. Wave 1 Feature List (Refined)

### Group A: api_main.py Bug Fixes & Performance

---

#### W1-001: Fix SCANNING vs SEARCH Bug in Autopilot Dispatch
**Files:**
- `src/python/api_main.py:275` — `_find_nearest_available_uav()`, change `"SCANNING"` to `"SEARCH"` in the list comprehension filter
- `src/python/vision/video_simulator.py:198` — `self._drone_mode: str = "SCANNING"` change to `"SEARCH"`

**Scope:**
- IN: Two string literal replacements + 3 unit tests
- OUT: No logic changes to UAV mode state machine

**Acceptance Criteria:**
- [ ] `"SCANNING"` replaced with `"SEARCH"` at `api_main.py:275` and `video_simulator.py:198`
- [ ] Demo autopilot dispatches SEARCH-mode drones to new targets
- [ ] 3 unit tests: (1) available UAV found when mode=SEARCH, (2) no UAV found when all non-SEARCH, (3) nearest by distance selected

---

#### W1-002: Fix Dead Enemy Cleanup Branch (Memory Leak)
**Files:**
- `src/python/api_main.py:300-324` — `enemy_intercept_dispatched` set and the `demo_autopilot()` enemy loop

**What's wrong:** Line 307 `if e.mode == "DESTROYED": continue` skips destroyed enemies before line 323 `elif e.mode == "DESTROYED"` can clean up the set.

**Scope:**
- IN: Move cleanup logic before the `continue` guard, or merge into the guard
- OUT: No changes to enemy UAV spawning or interception logic

**Acceptance Criteria:**
- [ ] `enemy_intercept_dispatched.discard(e.id)` executes when `e.mode == "DESTROYED"`
- [ ] Set is bounded after enemy destruction cycles
- [ ] Unit test: dispatch enemy, destroy it, verify set pruned

---

#### W1-004: Fix Silent ValueError Swallowing in Autopilot
**Files:**
- `src/python/api_main.py:344` — bare `except ValueError` in autopilot approve loop
- `src/python/api_main.py:426` — bare `except ValueError` in COA authorization
- `src/python/api_main.py:955,964,973,988,1002` — additional `except ValueError` blocks in `handle_payload()`

**Scope:**
- IN: Replace `except ValueError: pass` with `logger.exception("...")` at lines 344, 426. For lines 955-1002 in `handle_payload()`, these already have `exc` variables — verify they log, not silently pass.
- OUT: Do not change error handling semantics (still catch ValueError, just log it)

**Acceptance Criteria:**
- [ ] All `except ValueError: pass` at lines 344, 426 replaced with `logger.exception()`
- [ ] Failed COA authorizations visible in logs
- [ ] Unit test: trigger ValueError, verify logger called

---

#### W1-007: Fix Unbounded Memory Growth in TacticalAssistant
**Files:**
- `src/python/api_main.py:146` — `self._nominated: set = set()` in `TacticalAssistant.__init__()`
- `src/python/api_main.py:561` — `_prev_target_states: dict[int, str] = {}` module-level global

**Scope:**
- IN: Add TTL pruning to `_nominated` (remove targets not in current sim state). Clean `_prev_target_states` by intersecting with live target IDs each tick.
- OUT: Do not refactor TacticalAssistant class structure

**Acceptance Criteria:**
- [ ] `_nominated` pruned each tick: remove IDs not in `sim.targets`
- [ ] `_prev_target_states` pruned each tick: remove IDs not in current state
- [ ] Memory stable after 30 minutes of continuous operation (no unbounded growth)

---

#### W1-008: Cache get_state() Once Per Tick
**Files:**
- `src/python/api_main.py:598` — `async def simulation_loop()`
- Currently `sim.get_state()` called at lines 609, 627, 650, 691, 812

**Scope:**
- IN: Compute `state = sim.get_state()` once at top of tick, pass to all consumers
- OUT: Do not refactor simulation_loop into separate module (that's Wave 2)

**Acceptance Criteria:**
- [ ] Single `state = sim.get_state()` call per tick at top of `simulation_loop()`
- [ ] Cached state passed to broadcast, assessment worker, ISR queue, and TacticalAssistant
- [ ] No additional `get_state()` calls within a single tick iteration

---

#### W1-009: Replace O(N) Entity Lookups with Dict
**Files:**
- `src/python/sim_engine.py:663` — `_find_enemy_uav()` O(N) scan
- `src/python/sim_engine.py:669` — `_find_uav()` O(N) scan
- `src/python/sim_engine.py:675` — `_find_target()` O(N) scan
- These are called ~30+ times per tick (lines 682, 683, 706, 707, 718, 727, 738, 743, 1037, 1045, 1124, 1320, 1334, 1369, 1397, 1404, 1411)

**Scope:**
- IN: Change `self.uavs`, `self.targets`, `self.enemy_uavs` from lists to dicts keyed by ID. Update `_find_*` methods to O(1) dict lookups. Update all iteration to use `.values()`.
- OUT: Do not change public API of `SimulationModel.get_state()` — it can still return lists

**Acceptance Criteria:**
- [ ] Internal storage is `dict[int, UAV]`, `dict[int, Target]`, `dict[int, EnemyUAV]`
- [ ] `_find_uav()`, `_find_target()`, `_find_enemy_uav()` use `self.drones.get(id)`
- [ ] All iteration patterns use `.values()`
- [ ] All 475 existing tests pass
- [ ] `get_state()` output unchanged (returns lists for serialization)

---

#### W1-010: Move build_isr_queue() to Assessment Thread + Fix Event Logger
**Files:**
- `src/python/api_main.py:628` — `build_isr_queue()` called synchronously inside tick
- `src/python/event_logger.py:29` — `with open(log_path, "a") as f:` opens file every write
- `src/python/event_logger.py:34` — `def log_event()` function

**Scope:**
- IN: Move `build_isr_queue()` into the existing `asyncio.to_thread()` assessment worker. Refactor `event_logger.py` to keep file handle open, flush periodically.
- OUT: Do not change ISR queue algorithm or log format

**Acceptance Criteria:**
- [ ] `build_isr_queue()` runs in the background assessment thread, not blocking event loop
- [ ] `event_logger.py` keeps file handle open, uses periodic flush (e.g., every 5s or on buffer full)
- [ ] No synchronous blocking on event loop for ISR or logging

---

### Group B: Security Fixes

---

#### W1-011: WebSocket Message Size Guard
**Files:**
- `src/python/api_main.py` — `handle_payload()` or WebSocket receive loop (before `json.loads()`)

**Scope:**
- IN: Add `len(message) > 65536` check before `json.loads()`. Return structured error to client.
- OUT: Do not add authentication or rate limiting (those are later waves)

**Acceptance Criteria:**
- [ ] Messages > 64KB rejected before `json.loads()`
- [ ] Structured error JSON sent: `{"error": "message_too_large", "max_bytes": 65536}`
- [ ] Unit test: send oversized message, verify rejection

---

#### W1-012: Fix HITL Replay Attack
**Files:**
- `src/python/hitl_manager.py:192-215` — `_transition_entry()` method

**What's wrong:** No `old.status == "PENDING"` check before transition. A REJECTED entry can be replayed to APPROVED.

**Scope:**
- IN: Add `if old.status != "PENDING": raise ValueError(...)` guard in `_transition_entry()`. Log security event.
- OUT: Do not add auth/RBAC (that's Wave 4)

**Acceptance Criteria:**
- [ ] `_transition_entry()` rejects transitions from non-PENDING status with `ValueError`
- [ ] Attempted replays logged as security events via `logger.warning()`
- [ ] Unit test: create entry, reject it, attempt approve — verify ValueError raised

---

#### W1-013: Input Validation on All WebSocket Actions
**Files:**
- `src/python/api_main.py:112-121` — action schema definitions (partial)
- `src/python/api_main.py:1077-1080` — `set_coverage_mode` handler (no validation)
- `src/python/api_main.py:1005` — `verify_target` handler
- All `handle_payload()` action branches that accept lat/lon, confidence, theater, feed names

**Scope:**
- IN: Add validation functions/decorators for: coverage_mode (allowlist), lat/lon ([-90,90]/[-180,180], reject NaN/Inf), confidence ([0,1]), theater name (against `list_theaters()`), subscribe feed names (allowlist), SITREP query length (max 1000 chars). Return structured error on invalid input.
- OUT: Do not add Pydantic request models (that's Wave 2 refactor territory)

**Acceptance Criteria:**
- [ ] Coverage mode validated against known modes
- [ ] lat/lon reject NaN, Inf, out-of-range
- [ ] Confidence validated to [0,1]
- [ ] Theater name validated against `list_theaters()` allowlist
- [ ] Feed names validated against known feeds
- [ ] SITREP query length capped at 1000 chars
- [ ] All invalid inputs return `{"error": "validation_error", "field": "...", "reason": "..."}`

---

#### W1-014: Demo Autopilot Circuit Breaker
**Files:**
- `src/python/api_main.py:300+` — `demo_autopilot()` async function

**Scope:**
- IN: Add configurable limits: max approvals per minute (default 10), halt if no DASHBOARD client for 30s, per-session engagement cap (default 50). Log circuit breaker activations to Intel Feed as SAFETY events.
- OUT: Do not add operator authentication or multi-user support

**Acceptance Criteria:**
- [ ] Max N autonomous approvals per minute (configurable via env/config)
- [ ] Halt autopilot if no DASHBOARD client connected for 30+ seconds
- [ ] Per-session engagement count limit
- [ ] Circuit breaker events logged to Intel Feed with type="SAFETY"
- [ ] Unit tests for each breaker condition

---

### Group C: Agent Implementations

---

#### W1-003: Implement Three NotImplementedError Agents
**Files:**
- `src/python/agents/synthesis_query_agent.py:117` — `raise NotImplementedError`
- `src/python/agents/pattern_analyzer.py:79` — `raise NotImplementedError`
- `src/python/agents/battlespace_manager.py:167` — `raise NotImplementedError`
- Also found: `src/python/agents/ai_tasking_manager.py:61` — `raise NotImplementedError`

**Scope:**
- IN: Implement `_generate_response()` for all 4 agents using heuristic logic (no LLM required). `synthesis_query_agent` should query `sim.get_state()` and format a SITREP. `pattern_analyzer` should use existing `battlespace_assessment` functions. `battlespace_manager` should format zone/threat data. `ai_tasking_manager` should use ISR priority queue data.
- OUT: Do not add LLM integration (use heuristic/template approach). Do not refactor agent base class.

**Acceptance Criteria:**
- [ ] All 4 agents return meaningful responses (not NotImplementedError)
- [ ] `synthesis_query_agent.generate_sitrep()` returns formatted SITREP from sim state
- [ ] `pattern_analyzer.analyze_patterns()` returns activity patterns from assessment data
- [ ] `battlespace_manager.generate_mission_path()` returns zone/threat summary
- [ ] `ai_tasking_manager` returns sensor retasking recommendations
- [ ] 3+ unit tests per agent (12 total minimum)
- [ ] SITREP button in UI no longer crashes backend

---

### Group D: DevEx & CI

---

#### W1-015: pyproject.toml with Pinned Dependencies
**Files:**
- NEW: `pyproject.toml` (create at project root)
- EXISTING: `requirements.txt` (keep for backwards compat, pin versions)

**Scope:**
- IN: Create `pyproject.toml` with `[project]` metadata, pinned deps with upper bounds, `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` sections. Add `hypothesis`, `pip-audit` to dev deps. Set coverage threshold to 80%.
- OUT: Do not migrate to poetry/pdm. Do not remove `requirements.txt`.

**Acceptance Criteria:**
- [ ] `pyproject.toml` with pinned dependency versions
- [ ] ruff, mypy, pytest config sections
- [ ] 80% coverage threshold configured in `[tool.pytest.ini_options]`
- [ ] `hypothesis` in dev dependencies
- [ ] `pip-audit` in dev dependencies

---

#### W1-016: Pre-commit Hooks
**Files:**
- NEW: `.pre-commit-config.yaml` (create at project root)
- Depends on W1-015 for ruff/mypy config

**Scope:**
- IN: Configure pre-commit with ruff (lint+format), mypy (type check), eslint (frontend). Add `make lint` target.
- OUT: Do not add black separately (ruff handles formatting). Do not enforce on existing codebase if it causes >50 violations — use `--fix` on first run.

**Acceptance Criteria:**
- [ ] `.pre-commit-config.yaml` with ruff, mypy, eslint hooks
- [ ] `pre-commit run --all-files` passes (may need initial `--fix` pass)
- [ ] `make lint` target works

---

#### W1-017: GitHub Actions CI Pipeline
**Files:**
- NEW: `.github/workflows/test.yml`
- `src/python/api_main.py` — add `/health` endpoint

**Scope:**
- IN: GitHub Actions on push/PR: install deps, run ruff, run pytest with coverage, run frontend eslint. Add simple `/health` endpoint returning `{"status": "ok"}`. 80% coverage gate.
- OUT: Do not add deployment steps, Docker build, or integration testing in CI.

**Acceptance Criteria:**
- [ ] `.github/workflows/test.yml` triggers on push and PR to main
- [ ] Pipeline: ruff lint -> pytest with coverage -> eslint
- [ ] 80% coverage as blocking check
- [ ] `/health` GET endpoint returns `{"status": "ok"}`
- [ ] `/ready` GET endpoint returns `{"status": "ready", "components": {...}}`

---

#### W1-018: Makefile with Standard Targets
**Files:**
- NEW: `Makefile` (create at project root)

**Scope:**
- IN: Targets: `setup` (venv + pip install), `run` (palantir.sh), `demo` (palantir.sh --demo), `test` (pytest), `lint` (ruff + mypy), `build` (frontend npm build), `clean`.
- OUT: Do not add Docker targets (Wave 2).

**Acceptance Criteria:**
- [ ] `make setup` creates venv and installs deps
- [ ] `make run` launches palantir.sh
- [ ] `make demo` launches palantir.sh --demo
- [ ] `make test` runs pytest with coverage
- [ ] `make lint` runs ruff + mypy
- [ ] `make build` builds frontend
- [ ] Documented in README

---

### Group E: Testing

---

#### W1-019: Hypothesis Property-Based Tests
**Files:**
- NEW: `src/python/tests/test_property_sensor_fusion.py`
- NEW: `src/python/tests/test_property_verification.py`
- NEW: `src/python/tests/test_property_swarm.py`
- NEW: `src/python/tests/test_property_isr.py`
- EXISTING: `requirements.txt` — add `hypothesis`

**Scope:**
- IN: 10-15 `@given` property tests covering critical invariants:
  - `sensor_fusion.py`: fused confidence always in [0.0, 1.0], monotonically increases with more sensors
  - `verification_engine.py`: state never regresses (VERIFIED never goes back to DETECTED)
  - `swarm_coordinator.py`: no UAV assigned to two targets simultaneously
  - `isr_priority.py`: queue always sorted by descending priority score
  - Theater bounds: all generated positions within theater config bounds
- OUT: Do not test LLM-dependent agents. Do not add hypothesis to CI yet (W1-017 can include it).

**Acceptance Criteria:**
- [ ] `hypothesis` added to requirements
- [ ] 10-15 `@given` property tests passing
- [ ] Invariants: fusion in [0,1], no verification regression, no dual assignment, ISR sorted descending

---

### Group F: Frontend + Libraries

---

#### W1-006: Fix SampledPositionProperty Frontend Memory Leak
**Files:**
- `src/frontend-react/src/cesium/useCesiumDrones.ts:40,47,57,139,160,171` — drone SampledPositionProperty and SampledProperty addSample calls
- `src/frontend-react/src/cesium/useCesiumTargets.ts:70,76,123` — target SampledPositionProperty addSample calls

**Scope:**
- IN: After each `addSample()`, prune samples older than 60 seconds (keep max 600 samples per entity at 10Hz). Add helper function to prune `SampledPositionProperty` and `SampledProperty`.
- OUT: Do not refactor Cesium hooks. Do not change update frequency.

**Acceptance Criteria:**
- [ ] Rolling window pruner: keep only last 60 seconds of samples per entity (~600 samples)
- [ ] Applied to both drone position, drone orientation, and target position properties
- [ ] Demo runs 30+ minutes without Cesium performance degradation
- [ ] No visual glitching from pruning (smooth interpolation maintained)

---

#### W1-020: Add Shapely (Backend) and turf.js (Frontend) for Geometry
**Files:**
- `src/python/battlespace_assessment.py` — replace hand-rolled polygon/distance math with `shapely`
- `src/frontend-react/src/cesium/` hooks — replace inline trig with `@turf/turf`
- `requirements.txt` — add `shapely`
- `src/frontend-react/package.json` — add `@turf/turf`

**Scope:**
- IN: Add `shapely` to Python deps, use it in `battlespace_assessment.py` for polygon operations (zone containment, area calculation). Add `@turf/turf` to frontend, replace inline distance/bearing calculations.
- OUT: Do not rewrite all geometry code — replace only the most error-prone hand-rolled parts. Do not change zone model structure.

**Acceptance Criteria:**
- [ ] `shapely` used in `battlespace_assessment.py` for polygon containment/area
- [ ] `@turf/turf` used in at least 2 Cesium hooks replacing inline trig
- [ ] All 21 battlespace assessment tests pass
- [ ] All frontend builds cleanly

---

#### W1-023: UX Quick Fixes (Dead Buttons, Keyboard Shortcuts)
**Files:**
- `src/frontend-react/src/panels/assets/DroneActionButtons.tsx:37,53` — dead `onClick={() => {}}` on Range and Detail buttons
- NEW or existing component for keyboard shortcuts (likely `src/frontend-react/src/App.tsx` or a new `useKeyboardShortcuts.ts` hook)

**Scope:**
- IN: (1) Add `title="Coming soon"` + `disabled` to Range and Detail buttons, or hide them. (2) Add keyboard shortcuts: Escape=force MANUAL, A/R=approve/reject focused nomination, ?=show shortcut help overlay.
- OUT: Do not implement actual Range or Detail functionality. Do not add complex keybinding framework.

**Acceptance Criteria:**
- [ ] Dead buttons show "Coming soon" tooltip and are visually disabled
- [ ] Escape key sends `set_autonomy_level` MANUAL via WebSocket
- [ ] A/R keys approve/reject the top pending nomination
- [ ] ? key shows shortcut help overlay
- [ ] Shortcuts only active when no text input is focused

---

### Group G: Algorithms + RTB

---

#### W1-021: KD-Tree Clustering (scipy.spatial)
**Files:**
- `src/python/battlespace_assessment.py` — replace O(n^2) distance loop in clustering with `scipy.spatial.KDTree`
- `requirements.txt` — add `scipy` (if not already present)

**Scope:**
- IN: Replace the O(n^2) pairwise distance computation in threat clustering with `KDTree.query_ball_point()` or `KDTree.query_pairs()`.
- OUT: Do not change clustering algorithm logic (thresholds, grouping). Do not change output format.

**Acceptance Criteria:**
- [ ] `scipy.spatial.KDTree` used for distance queries in clustering
- [ ] All 21 battlespace assessment tests pass
- [ ] Same clustering results (algorithm equivalent, just faster data structure)

---

#### W1-022: Fix RTB Mode with Real Return Logic
**Files:**
- `src/python/sim_engine.py:386-387` — `elif self.mode == "RTB":` with comment "Placeholder — drift slowly for now"
- `src/python/sim_engine.py:397-398` — fuel-triggered RTB transition

**Scope:**
- IN: Give each UAV a `home_position` (from initial spawn position or theater config `base_location` if available). In RTB mode, use existing `_turn_toward()` to navigate to home_position. Transition to IDLE when within threshold distance (e.g., 500m).
- OUT: Do not add fuel consumption model beyond existing `fuel_hours`. Do not add landing animations.

**Acceptance Criteria:**
- [ ] Each UAV has `home_position` attribute (set at spawn)
- [ ] RTB mode navigates toward `home_position` using `_turn_toward()`
- [ ] UAV transitions to IDLE when within 500m of home
- [ ] Unit tests: RTB navigates home, transitions to IDLE on arrival

---

### Group H: Cleanup

---

#### W1-005: Delete or Gut pipeline.py Dead Code
**Files:**
- `src/python/pipeline.py` — 124 lines, blocking `input()` at line 81, never called from WebSocket flow
- `src/python/tests/test_data_synthesizer.py` — references non-existent `/ingest` endpoint (if exists)

**Scope:**
- IN: Delete `pipeline.py` entirely, or gut to a stub with docstring: "F2T2EA pipeline is implemented in api_main.py demo_autopilot(). This file is retained as a reference." Clean up any test files referencing removed code.
- OUT: Do not touch `api_main.py` autopilot logic.

**Acceptance Criteria:**
- [ ] `pipeline.py` deleted or reduced to stub with redirect docstring
- [ ] No imports of `pipeline.py` remain in codebase
- [ ] `test_data_synthesizer.py` cleaned if it references dead endpoints
- [ ] All existing tests pass

---

## 2. Builder Groups for Parallel Execution

Features are grouped to **minimize file conflicts** between parallel builders.

| Group | Features | Primary Files | Builder Focus |
|-------|----------|---------------|---------------|
| **A** | W1-001, W1-002, W1-004, W1-007, W1-008, W1-010 | `api_main.py`, `event_logger.py` | Backend bugs + performance |
| **B** | W1-011, W1-012, W1-013, W1-014 | `api_main.py` (WS receive), `hitl_manager.py` | Security hardening |
| **C** | W1-003 | `agents/*.py` (4 files) | Agent implementations |
| **D** | W1-015, W1-016, W1-017, W1-018 | `pyproject.toml`, `.pre-commit-config.yaml`, `.github/`, `Makefile` | DevEx & CI (new files only) |
| **E** | W1-019 | `tests/test_property_*.py` (new files) | Property-based testing |
| **F** | W1-006, W1-020, W1-023 | `cesium/*.ts`, `battlespace_assessment.py`, `DroneActionButtons.tsx` | Frontend + geometry libs |
| **G** | W1-021, W1-022 | `battlespace_assessment.py`, `sim_engine.py` | Algorithms + RTB |
| **H** | W1-005 | `pipeline.py` | Cleanup (trivial, any builder) |

### Conflict Analysis

| Conflict | Groups | Resolution |
|----------|--------|------------|
| `api_main.py` | A vs B | **SERIALIZE A before B.** Group A changes line numbers and function structure; Group B adds validation guards. B should start after A merges. |
| `battlespace_assessment.py` | F (shapely) vs G (KDTree) | **SAFE IN PARALLEL.** Shapely replaces polygon ops; KDTree replaces distance computation. Different functions, no overlap. |
| `sim_engine.py` | A (W1-009 dict) vs G (W1-022 RTB) | **SAFE IN PARALLEL.** W1-009 changes storage structure; W1-022 changes RTB mode behavior in `_update_kinematics()`. Different code sections. |
| `requirements.txt` | D, E, F, G | **LAST MERGE WINS.** Each group adds deps independently. Merge conflicts are trivial (additive lines). |

### Recommended Execution Order

```
Wave 1a (parallel, immediate):
  Group C — Agents          (independent, no conflicts)
  Group D — DevEx/CI        (new files only, no conflicts)
  Group E — Property tests  (new files only, no conflicts)
  Group F — Frontend + libs (frontend + battlespace_assessment, no api_main)
  Group G — Algorithms      (sim_engine + battlespace_assessment, no api_main)
  Group H — Cleanup         (pipeline.py only, trivial)

Wave 1b (parallel, after 1a Group A):
  Group A — api_main bugs   (changes api_main structure)

Wave 1c (after Group A merges):
  Group B — Security        (adds guards to api_main, needs stable line numbers)
```

**Optimal with 4 builders:**
- Builder 1: Group A then Group B (sequential, ~1.5 days)
- Builder 2: Group C + Group H (~1 day)
- Builder 3: Group D + Group E (~1 day)
- Builder 4: Group F + Group G (~1 day)

---

## 3. Dependency Map

Most Wave 1 features are independent. The few dependencies:

```
W1-015 (pyproject.toml)
  └── W1-016 (pre-commit hooks) — needs ruff/mypy config from pyproject.toml
       └── W1-017 (CI pipeline) — should match pre-commit tool versions

W1-009 (dict lookups in sim_engine)
  └── W1-022 (RTB fix) — if modifying UAV dataclass, coordinate with dict change
       (SAFE IN PARALLEL if W1-022 only adds home_position attribute)

Group A (api_main.py changes)
  └── Group B (security additions) — Group B should build on top of Group A's changes
       to avoid merge conflicts in api_main.py

W1-019 (hypothesis tests)
  └── depends on: hypothesis added to requirements (W1-015)
       (can install independently, just needs to be in final requirements)
```

**Critical path:** Group A -> Group B (everything else is independent)

All other features (W1-001 through W1-023) have NO inter-dependencies and can execute in any order.

---

## 4. Risk Register — Wave 1

| # | Risk | Severity | Likelihood | Affected Features | Mitigation |
|---|------|----------|------------|-------------------|------------|
| R1 | **W1-009 (dict conversion) breaks 475 tests** — changing `self.uavs` from list to dict touches every test that constructs a SimulationModel | HIGH | MEDIUM | W1-009, all groups | Run full test suite after dict conversion before proceeding. Keep `get_state()` returning lists. If >20 tests break, consider wrapper approach instead. |
| R2 | **Group A + Group B merge conflicts in api_main.py** — both groups modify the same 1100-line file extensively | HIGH | HIGH | W1-001 to W1-014 | Serialize: Group A completes and merges first, Group B rebases on top. Do NOT run in parallel. |
| R3 | **W1-006 (SampledPositionProperty pruning) causes visual glitches** — pruning samples from Cesium's interpolation property may cause position jumps | MEDIUM | MEDIUM | W1-006 | Test with 60s window first. If glitching occurs, increase to 120s (1200 samples). Use `setInterpolationOptions` with Lagrange interpolation. |
| R4 | **W1-003 (agent implementations) scope creep** — 4 agents need heuristic implementations; temptation to add LLM integration | MEDIUM | HIGH | W1-003 | STRICT scope: heuristic/template responses only. Each agent implementation must be <100 lines. No LLM calls, no API keys needed. |
| R5 | **W1-016 (pre-commit hooks) fails on existing codebase** — ruff/mypy may flag hundreds of existing violations | MEDIUM | HIGH | W1-016 | Run `ruff check --fix` first to auto-fix. For mypy, start with `--ignore-missing-imports` and minimal strictness. Do NOT block on pre-existing violations — use baseline/ignore approach. |

---

## 5. Success Criteria for Wave 1 Completion

All of the following must be true before advancing to Wave 2:

- [ ] `./palantir.sh --demo` runs a full F2T2EA cycle with drones dispatching to targets (W1-001 fix verified)
- [ ] All 475 existing tests pass + new tests bring coverage toward 80%
- [ ] No `NotImplementedError` in any agent (W1-003)
- [ ] No `except ValueError: pass` in api_main.py (W1-004)
- [ ] No unbounded memory growth in 30-minute demo session (W1-002, W1-006, W1-007)
- [ ] WebSocket input validation rejects malformed inputs (W1-013)
- [ ] HITL replay attack closed (W1-012)
- [ ] Demo autopilot has circuit breaker safety limits (W1-014)
- [ ] `make test` and `make lint` work from clean checkout (W1-015, W1-016, W1-018)
- [ ] CI pipeline runs on PR (W1-017)
- [ ] RTB mode navigates drones home (W1-022)
- [ ] Property tests validate simulation invariants (W1-019)
