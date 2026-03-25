# CODEBASE_STATE.md — Wave 1 Builder Reference

**Generated:** 2026-03-20 | **For:** Wave 1 builders (W1-001 through W1-023)

All line numbers verified against current codebase. This document is authoritative.

---

## 1. `src/python/api_main.py` — 1,113 lines

### Key locations for Wave 1

| Feature | Symbol | Lines | Notes |
|---------|--------|-------|-------|
| W1-001 SCANNING bug | `_find_nearest_available_uav()` | 270–279 | **Bug at line 275**: `"SCANNING"` should be `"SEARCH"` |
| W1-002 Dead enemy cleanup | `demo_autopilot()` enemy loop | 306–324 | `elif e.mode == "DESTROYED"` at line 323 is **unreachable** — continue guard at line 307 skips it |
| W1-004 ValueError swallowing | `demo_autopilot()` COA block | 424–427 | `except ValueError: pass` — silent failure |
| W1-007 `_nominated` set | `TacticalAssistant.__init__` | 141–147 | `self._nominated: set = set()` at line 146 — never pruned |
| W1-007 `_prev_target_states` | module-level | 561 | `_prev_target_states: dict[int, str] = {}` — never cleaned |
| W1-008 `get_state()` redundant call | `simulation_loop()` | 609, 627, 650 | Three separate `get_state()` calls: lines 609, 627, 650 — should be one |
| W1-011 WebSocket size guard | `websocket_endpoint()` | 780–798 | No message size check before `json.loads(data)` at line 792 |
| W1-013 Input validation gaps | `handle_payload()` | 901–1111 | `set_coverage_mode` at 1077–1080: no allowlist check; lat/lon: no NaN/Inf guard; theater names: no validation |
| W1-014 Demo autopilot circuit breaker | `demo_autopilot()` | 282–442 | No max approval rate, no dead-man disconnect check |
| W1-017 Missing `/health` endpoint | (absent) | — | Not present; needs adding |

### `_find_nearest_available_uav()` — exact bug (line 275)
```python
# CURRENT (WRONG) — line 275:
available = [u for u in sim.uavs if u.mode in ("IDLE", "SCANNING")]

# FIXED:
available = [u for u in sim.uavs if u.mode in ("IDLE", "SEARCH")]
```

### Dead enemy cleanup — unreachable branch (lines 306–324)
```python
for e in sim.enemy_uavs:
    if e.mode == "DESTROYED":        # line 307 — continue guard
        continue
    if e.id in enemy_intercept_dispatched:
        continue
    if e.fused_confidence > 0.7:
        ...
        enemy_intercept_dispatched.add(e.id)
        ...
    elif e.mode == "DESTROYED" and e.id in enemy_intercept_dispatched:   # line 323 — UNREACHABLE
        enemy_intercept_dispatched.discard(e.id)
```
Fix: remove the `continue` at 307, restructure so DESTROYED cleanup executes.

### Silent ValueError (lines 424–427)
```python
try:
    hitl.authorize_coa(entry_id, best_coa.id, "Demo auto-authorized")
except ValueError:
    pass    # line 427 — BUG: should be logger.exception(...) + fallback
```

### `get_state()` triple call in `simulation_loop()` (lines 598–685)
- Line 609: `state_snapshot = sim.get_state()` (inside `if now - _last_assessment_time >= 5.0` block)
- Line 627: `state_snap = sim.get_state()` (second call, also in 5s block — to build ISR queue)
- Line 650: `state = sim.get_state()` (third call — main broadcast, every tick)

Fix for W1-008: cache result at top of tick, pass to all consumers. ISR queue call on line 627 should reuse `state_snapshot` from line 609.

### Import chain
```python
from sim_engine import SimulationModel           # line 20
from pipeline import F2T2EAPipeline             # line 31 — dead import (W1-005)
pipeline = F2T2EAPipeline(llm_client=None, ...)  # line 129 — dead instantiation
```

### `_ACTION_SCHEMAS` dict — lines 100–122
Used by `_validate_payload()`. Already covers lat/lon as `"float"` type but does NOT validate ranges (NaN, Inf, bounds). `set_coverage_mode`, `subscribe`, `subscribe_sensor_feed` not in schema at all.

### `sim` and `hitl` globals — lines 520–522
```python
sim = SimulationModel(theater_name=settings.default_theater)  # line 520
sim.demo_fast = settings.demo_mode                            # line 521
hitl = HITLManager()                                          # line 522
clients = {}                                                   # line 523
```

### `_handle_sitrep_query()` — lines 807–856
Heuristic SITREP already implemented inline here and at `post_sitrep()` (lines 687–724). Both duplicate logic. The `SynthesisQueryAgent.generate_sitrep()` is NOT called here — it's bypassed by the heuristic path. W1-003 should wire the agent properly but keep heuristic as fallback.

---

## 2. `src/python/sim_engine.py` — 1,553 lines

### Data structures — LISTS, not dicts (critical for W1-009)
```python
self.uavs: List[UAV] = []         # line 524 — initialized in __init__
self.targets: List[Target] = []    # line 573
self.enemy_uavs: List[EnemyUAV] = []  # line 574
```
All three are **Python lists**. `_find_uav()`, `_find_target()`, `_find_enemy_uav()` all do O(N) linear scans.

### `_find_uav()` — lines 669–673
```python
def _find_uav(self, uav_id: int) -> Optional[UAV]:
    for u in self.uavs:
        if u.id == uav_id:
            return u
    return None
```

### `_find_target()` — lines 675–679
```python
def _find_target(self, target_id: int) -> Optional[Target]:
    for t in self.targets:
        if t.id == target_id:
            return t
    return None
```

### `_find_enemy_uav()` — lines 663–667
```python
def _find_enemy_uav(self, enemy_uav_id: int) -> Optional[EnemyUAV]:
    for e in self.enemy_uavs:
        if e.id == enemy_uav_id:
            return e
    return None
```

### RTB mode — placeholder drift logic — lines 386–391
```python
elif self.mode == "RTB":
    # Placeholder — drift slowly for now
    self.vx *= 0.98
    self.vy *= 0.98
    self.x += self.vx * dt_sec
    self.y += self.vy * dt_sec
```
**No home position concept exists.** UAVs have no `home_position` attribute. For W1-022: add `home_position: Tuple[float, float]` to `UAV.__init__`, set it at spawn time (line 601), then replace the drift code with `_turn_toward()` logic.

### UAV class — key attributes (lines 273–315)
- `self.mode = "IDLE"` — starting mode
- `self.sensors: List[str]` — list of sensor types (e.g. `["EO_IR", "SAR"]`)
- `self.autonomy_override: Optional[str]` — per-drone autonomy level override
- `self.primary_target_id: Optional[int]` — current primary tracked target
- NO `home_position` attribute currently

### IDLE/SEARCH loiter logic — lines 365–384
Both `"IDLE"` and `"SEARCH"` share the same loiter pattern (fixed-wing circle). This is intentional — they behave identically in physics, differentiated only by semantic meaning.

### `_turn_toward()` method — lines 317–331
Available on `UAV`. Takes `(target_vx, target_vy, speed, dt_sec)`. Use this for RTB navigation.

### `autonomous_transitions` dict — lines 50–59
Maps `(current_mode, trigger) -> new_mode`. Used by autonomy dispatch. Note: swarm coordinator currently ignores this (CR-4 conflict resolved in Wave 2).

---

## 3. `src/python/agents/battlespace_manager.py` — 225 lines

### NotImplementedError location — line 167
```python
def _generate_response(self, query: str) -> str:
    ...
    raise NotImplementedError("LLM integration needs to be completed.")
```

### What `generate_mission_path()` does (lines 69–124)
Calls `_generate_response()` then post-processes waypoints using `filter_safe_waypoints()` from `utils.geo_utils`. The crash happens before post-processing — fix `_generate_response()` to return a heuristic JSON payload when llm_client is None.

### Existing infrastructure to leverage
- `_default_layers()` (lines 191–225): returns 5 map layers — works fine
- `get_active_layers()` (line 126): works fine
- `update_threat_rings()` (lines 130–146): works fine
- `self._threat_rings`, `self._map_layers` — internal state

### Heuristic fix strategy
`_generate_response()` should check `if self.llm_client is None` and return a minimal valid JSON string matching `BattlespaceManagerOutput` schema, assembled from the `tracks` and `threat_rings` inputs. The method receives `query: str` which contains embedded JSON of the tracks and threats.

---

## 4. `src/python/agents/pattern_analyzer.py` — 88 lines

### NotImplementedError location — line 79
```python
def _generate_response(self, historical_data: str) -> str:
    ...
    raise NotImplementedError("LLM integration needs to be completed.")
```

### `analyze_patterns()` — lines 81–88
Calls `get_activity_summary(sector)` from `mission_data.historical_activity`, passes result to `_generate_response()`, then validates JSON against `PatternAnalyzerOutput`.

### Heuristic fix strategy
`_generate_response()` should parse `historical_data` string (it's text from `get_activity_summary()`), build a minimal `PatternAnalyzerOutput`-compatible JSON with at least one placeholder anomaly, and return it. Check `mission_data/historical_activity.py` for what `get_activity_summary()` returns.

---

## 5. `src/python/agents/synthesis_query_agent.py` — 137 lines

### NotImplementedError location — line 117
```python
def _generate_response(self, query: str, context_json: str) -> str:
    ...
    raise NotImplementedError("LLM integration needs to be completed.")
```

### `generate_sitrep()` — lines 121–137
Already has `_build_context_payload()` to serialize tracks/nominations/BDA.

### Key insight
`api_main.py` already has a complete heuristic SITREP builder in `_handle_sitrep_query()` (lines 807–856) and `post_sitrep()` (lines 687–724). The fix for W1-003 should wire the heuristic from api_main.py into the agent's `_generate_response()` (or make `generate_sitrep()` call sim state directly when llm_client is None).

### `SITREPQuery` schema (from ontology)
Has fields: `query`, `context_tracks`, `context_nominations`, `context_bda`. All optional except `query`.

---

## 6. `src/python/pipeline.py` — 124 lines

### Blocking `input()` — line 81
```python
decision = input("  [A]pprove / [R]eject / Re[T]ask -> ").strip().upper()
```

### Status: DEAD CODE
- Never called in the WebSocket flow
- `api_main.py` imports it (line 31) and instantiates it (line 129) but never calls `.run()`
- Real pipeline runs through `TacticalAssistant` + `HITLManager` in api_main.py

### W1-005 resolution
Either: (a) Delete `pipeline.py` entirely and remove the import/instantiation in api_main.py lines 31 and 129, OR (b) gut to a stub module with a docstring only. The test file `test_data_synthesizer.py` references a non-existent `/ingest` endpoint and should be cleaned up alongside.

---

## 7. `src/python/hitl_manager.py` — 222 lines

### `_transition_entry()` — lines 192–215
```python
def _transition_entry(self, entry_id: str, new_status: str, rationale: str) -> StrikeBoardEntry:
    idx, old = self._find_entry(entry_id)
    updated = replace(old, status=new_status, decision=_make_decision(new_status, rationale))
    ...
```

### W1-012 HITL replay attack
**Bug:** `_transition_entry()` does NOT check `old.status == "PENDING"` before transitioning. A REJECTED entry can be re-approved by calling `approve_nomination(entry_id, ...)` again.

**Fix:** Add guard at line 199, before the `replace()` call:
```python
if old.status != "PENDING":
    raise ValueError(f"Cannot transition entry {entry_id} from status {old.status!r}")
```

### Immutability pattern
`StrikeBoardEntry` and `CourseOfAction` are `frozen=True` dataclasses (lines 30–55). All mutations use `replace()` from `dataclasses`. This is correct and should be preserved.

### `_strike_board` uses list spread to remain immutable
```python
self._strike_board = [*self._strike_board, entry]   # line 101
self._coa_proposals = {**self._coa_proposals, entry_id: list(coas)}  # line 121
```
Immutable-style replacements — pattern to preserve.

---

## 8. `src/python/event_logger.py` — 83 lines

### File handle pattern — lines 27–31 (W1-010)
```python
async def _writer_loop() -> None:
    ...
    while True:
        event = await _queue.get()
        log_path = LOG_DIR / f"events-{date.today().isoformat()}.jsonl"
        with open(log_path, "a") as f:          # line 29 — opens file on EVERY event
            f.write(json.dumps(event, default=str) + "\n")
        _queue.task_done()
```

**Bug:** Opens and closes the file handle on every single event write. At 10Hz simulation rate this is a syscall per tick.

**Fix strategy:** Keep file handle open in the writer loop, only reopen when the date changes (for daily rotation). Cache the current date and reopen when `date.today()` differs.

---

## 9. `src/python/battlespace_assessment.py` — 329 lines

### Clustering algorithm — lines 118–170
Current algorithm: O(n²) double loop — for each anchor target, iterate ALL detected targets to find neighbors within `CLUSTER_RADIUS_DEG = 0.135`.

```python
def _cluster_targets(self, targets: List[dict]) -> List[ThreatCluster]:
    detected = [t for t in targets if t.get("state", "UNDETECTED") != "UNDETECTED"]
    ...
    for i, anchor in enumerate(detected):
        ...
        neighbors = [
            t for t in detected                           # O(n) inner loop
            if math.hypot(_get_xy(t)[0] - ax, _get_xy(t)[1] - ay) <= CLUSTER_RADIUS_DEG
        ]
```

**W1-021 fix:** Replace inner loop with `scipy.spatial.KDTree`. Build tree from `[_get_xy(t) for t in detected]`, then use `tree.query_ball_point([ax, ay], CLUSTER_RADIUS_DEG)` to get neighbor indices in O(log n).

### Convex hull algorithm — lines 284–329
Jarvis march (gift-wrapping), O(nh) where h = hull points. For small n (≤ 20 targets typical in demo), this is fine. Do NOT replace in Wave 1.

### Other methods and their complexity
- `_identify_coverage_gaps()`: O(targets × zones) — small, fine
- `_score_zone_threats()`: O(targets × zones) — small, fine
- `_detect_movement_corridors()`: O(targets × history) — fine

---

## 10. `src/python/sensor_model.py` — 263 lines

### `altitude_penalty` — documented but unused — line 167
```python
# snr_norm = (1 - (range/max_range)^2)
#            + rcs_gain * 0.3
#            - altitude_penalty          (unused; kept for future)
#            - weather_penalty
```

The comment says `altitude_penalty` is kept for future use. The actual formula in `compute_pd()` (lines 154–197) does NOT include altitude_penalty in the calculation — it's simply not there. This is intentional per CONSENSUS.md (W2-001 says "altitude_penalty in sensor_model.py applied" — left for Wave 2 architecture refactor).

**Do not add altitude_penalty in Wave 1** — it's a Wave 2 concern.

---

## 11. Frontend Files

### `src/frontend-react/src/cesium/useCesiumDrones.ts` — 223 lines

#### W1-006 SampledPositionProperty memory leak
- **Line 40:** `new Cesium.SampledPositionProperty()` — created per drone entity on first spawn
- **Line 47:** `positionProperty.addSample(viewer.clock.currentTime, position)` — initial sample
- **Line 139:** `(marker.position as Cesium.SampledPositionProperty).addSample(targetTime, position)` — called EVERY tick (10Hz per drone)
- **Line 160–171:** Orientation samples also added every tick

**No pruning exists.** After 10 minutes at 10Hz = 6,000 samples per drone × 10 drones = 60,000 samples.

**Fix:** After each `addSample()` call, prune old samples. Pattern:
```typescript
const prop = marker.position as Cesium.SampledPositionProperty;
prop.addSample(targetTime, position);
// Keep only last 60 seconds (600 samples at 10Hz)
const cutoff = Cesium.JulianDate.addSeconds(now, -60, new Cesium.JulianDate());
prop.removeSamples(new Cesium.TimeInterval({ start: Cesium.JulianDate.fromIso8601('2000-01-01'), stop: cutoff }));
```

#### Tether — `CallbackProperty` (lines 109–128)
The tether (vertical line from drone to ground) uses `Cesium.CallbackProperty` which evaluates at 60fps. For W1-006 this should be computed at 10Hz tick rate instead, using `ConstantProperty` updated each tick.

### `src/frontend-react/src/cesium/useCesiumTargets.ts` — 235 lines
- **Line 70:** `new Cesium.SampledPositionProperty()` — same pattern as drones
- **Line 76:** initial sample
- **Line 123:** `addSample(targetTime, position)` per tick — same leak
- Same fix applies as for drones

### `src/frontend-react/src/panels/assets/DroneActionButtons.tsx` — 70 lines
#### W1-023 Dead buttons
- **Line 37:** `onClick={() => {}}` — "Range" button (dead)
- **Line 53:** `onClick={() => {}}` — "Detail" button (dead)

Fix: Replace with tooltip "Coming soon" or hide entirely. Do NOT add real functionality in Wave 1.

### `src/frontend-react/src/cesium/useCesiumMacroTrack.ts` — 73 lines
Uses `SampledPositionProperty` — check if same leak applies.

---

## 12. Existing Test Patterns

### Location
All tests in `src/python/tests/` (23 files, ~6,523 lines total).

### `conftest.py` — 9 lines
```python
# Inserts src/python into sys.path so bare imports work
_SRC = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _SRC)
```
No fixtures in conftest — all fixtures are local to each test file.

### Test naming convention
- Files: `test_<module_name>.py`
- Classes: `Test<FunctionName>` (e.g., `class TestDegToMeters:`)
- Methods: `test_<scenario_description>` (e.g., `def test_same_point_returns_zero()`)

### Fixture pattern
Pytest fixtures, function-scoped, defined at module level:
```python
@pytest.fixture
def manager():
    return HITLManager()

@pytest.fixture
def sample_target_data():
    return {...}
```

### Factory helper pattern
Helper functions prefixed with `_make_`:
```python
def _make_target(id, x, y, target_type="SAM", state="DETECTED", ...):
    return {...}

def _make_zone(x_idx, y_idx, lon, lat, uav_count=0):
    return {...}

def _make_uav(id, lon, lat, mode="SEARCH", ...):
    return {...}
```

### Assertion style
- Direct `assert` statements (no unittest-style)
- `pytest.raises(SomeError)` for exception tests
- `abs(result - expected) < tolerance` for float comparisons

### Import style
Direct imports from module (no package prefix):
```python
from battlespace_assessment import BattlespaceAssessor, ThreatCluster
from hitl_manager import CourseOfAction, HITLManager
from sensor_model import compute_pd, evaluate_detection
```

### Coverage target
80% minimum (per pyproject.toml, though pyproject.toml doesn't exist yet — W1-015 adds it).

---

## 13. Code Conventions & Import Patterns

### Python backend
- Frozen immutable dataclasses throughout (`frozen=True`)
- Structlog for all logging: `logger = structlog.get_logger()` at module top
- Pydantic for API schemas
- `from __future__ import annotations` used in some files
- Constants defined as module-level ALL_CAPS
- No type hints added to code outside of changes
- All public types in `src/python/schemas/ontology.py` (Pydantic) and `src/python/core/ontology.py` (LangGraph)

### Frontend
- React hooks pattern: `useEffect` + `useRef` for Cesium entity lifecycle
- Zustand store: `useSimStore` from `../store/SimulationStore`
- TypeScript strict mode
- Blueprint.js dark theme components
- No `console.log` in production code (use structlog on backend; frontend has no logger convention yet)

### Config constants already defined in sim_engine.py
```python
CLUSTER_RADIUS_DEG = 0.135          # battlespace_assessment.py
MIN_CLUSTER_SIZE = 2
MAX_TURN_RATE = math.radians(3.0)   # sim_engine.py
DEG_PER_KM = 1.0 / 111.0
SUPERVISED_TIMEOUT_SEC = 10.0
BDA_DURATION_SEC = 30.0
```

---

## 14. Wave 1 Feature-to-File Mapping

| Feature | Files Modified |
|---------|---------------|
| W1-001 SCANNING→SEARCH | `api_main.py:275`, `video_simulator.py:198` |
| W1-002 Dead enemy cleanup | `api_main.py:306–324` |
| W1-003 NotImplementedError agents | `agents/battlespace_manager.py:167`, `agents/pattern_analyzer.py:79`, `agents/synthesis_query_agent.py:117` |
| W1-004 ValueError swallowing | `api_main.py:424–427` (and other except ValueError blocks in autopilot) |
| W1-005 Delete pipeline.py | `pipeline.py`, `api_main.py:31,129` |
| W1-006 SampledPositionProperty | `cesium/useCesiumDrones.ts:139–171`, `cesium/useCesiumTargets.ts:123` |
| W1-007 _nominated / _prev_target_states | `api_main.py:141–147` (TacticalAssistant), `api_main.py:561` |
| W1-008 Cache get_state() | `api_main.py:598–685` (simulation_loop) |
| W1-009 Dict lookups | `sim_engine.py:524,573,574` (data structures) + all `_find_*()` methods + all call sites |
| W1-010 ISR queue + event logger | `api_main.py:606–644` (assessment block), `event_logger.py:27–31` |
| W1-011 WS message size guard | `api_main.py:780–798` |
| W1-012 HITL replay attack | `hitl_manager.py:192–215` (_transition_entry) |
| W1-013 Input validation | `api_main.py:1037–1111` (handle_payload validation) |
| W1-014 Demo autopilot circuit breaker | `api_main.py:282–442` (demo_autopilot) |
| W1-015 pyproject.toml | New file: `pyproject.toml` |
| W1-016 Pre-commit hooks | New file: `.pre-commit-config.yaml` |
| W1-017 GitHub Actions CI | New file: `.github/workflows/test.yml` + `api_main.py` (/health endpoint) |
| W1-018 Makefile | New file: `Makefile` |
| W1-019 Hypothesis tests | New test file: `tests/test_invariants.py` (or add to existing test files) |
| W1-020 Shapely / turf.js | `battlespace_assessment.py`, `requirements.txt`, frontend package.json |
| W1-021 KD-Tree clustering | `battlespace_assessment.py:118–170` (_cluster_targets method) |
| W1-022 RTB mode | `sim_engine.py:386–391` (UAV.update RTB block), `sim_engine.py:273–315` (UAV.__init__) |
| W1-023 Dead buttons / shortcuts | `panels/assets/DroneActionButtons.tsx:37,53`, new keyboard handler component |

---

## 15. Critical Dependencies Between Wave 1 Features

**W1-009 dict refactor affects W1-001, W1-002, W1-007, W1-008, W1-022:**
If W1-009 (dict lookup refactor) runs first, all `sim.uavs` list iterations in api_main.py become `sim.uavs.values()`. If W1-009 runs after, builders using list-style iteration are safe. **Coordinate execution order.**

**W1-005 (delete pipeline.py) is safe to run independently** — just remove lines 31 and 129 from api_main.py and delete the file.

**W1-003 (NotImplementedError agents) does NOT affect api_main.py** — the heuristic SITREP path in `_handle_sitrep_query()` bypasses `SynthesisQueryAgent.generate_sitrep()` entirely. The agent fix is additive.

**W1-012 (HITL replay) affects existing hitl tests** — 18 test scenarios in `tests/test_hitl_manager.py`. The guard should not break any existing tests (they all start with PENDING entries).
