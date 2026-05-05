# Code Review — Wave 5 Changes

**Review Date:** 2026-03-22
**Commit Range:** ad9b42c..HEAD
**Reviewer:** python-reviewer agent
**Test status:** 323 passed, 0 failed

---

## Files Reviewed

| File | Type | Lines |
|------|------|-------|
| `src/python/checkpoint.py` | New | 134 |
| `src/python/hitl_manager.py` | Modified | ~230 |
| `src/python/jammer_model.py` | New | 149 |
| `src/python/llm_sanitizer.py` | New | 162 |
| `src/python/rbac.py` | New | 177 |
| `src/python/report_generator.py` | New | 188 |
| `src/python/scenario_engine.py` | New | 217 |
| `src/python/sensor_model.py` | Modified | 500 |
| `src/python/sim_controller.py` | New | 77 |
| `src/python/terrain_model.py` | New | 221 |
| `src/python/uav_logistics.py` | New | 101 |
| `src/python/weather_engine.py` | New | 155 |
| Tests | New | 10 files, 323 tests |

---

## Findings

### CRITICAL

None.

---

### HIGH

**H1 — `rbac.py`: Default `AUTH_DISABLED=True` ships in production**
File: `src/python/rbac.py:22`

```python
AUTH_DISABLED: bool = os.environ.get("AUTH_DISABLED", "true").lower() in ("true", "1", "yes")
```

The default is `"true"` — auth is bypassed unless the operator explicitly sets `AUTH_DISABLED=false`. Any deployment that does not set the env var runs with full ADMIN privileges for all connections. For a C2 system this is an unacceptable insecure default.

**Fix:** Change default to `"false"`:
```python
AUTH_DISABLED: bool = os.environ.get("AUTH_DISABLED", "false").lower() in ("true", "1", "yes")
```

---

**H2 — `rbac.py`: Dev JWT secret is too short and hardcoded**
File: `src/python/rbac.py:23`

```python
JWT_SECRET: str = os.environ.get("JWT_SECRET", "grid_sentinel-dev-secret")
```

`"grid_sentinel-dev-secret"` is 20 bytes — below the 32-byte minimum for HS256 (PyJWT emits `InsecureKeyLengthWarning` in tests). The fallback makes the secret predictable in any environment where `JWT_SECRET` is not set. If H1 is fixed, this becomes a direct attack vector.

**Fix:** Remove the fallback — raise at import time if secret is absent and auth is enabled:
```python
JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
if not AUTH_DISABLED and len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 bytes when AUTH_DISABLED is false")
```

---

### MEDIUM

**M1 — `rbac.py` tests: Short JWT secrets generate persistent warnings**
File: `src/python/tests/test_rbac.py`

Tests use secrets like `"s"`, `"abc"`, `"test-secret"` — all below 32 bytes. PyJWT 2.x emits `InsecureKeyLengthWarning` for each call, producing 11 warnings in the test run. Use a ≥32-byte constant across all test JWT calls.

---

**M2 — `scenario_engine.py`: `ScenarioEvent.params` is a mutable dict inside a frozen dataclass**
File: `src/python/scenario_engine.py:65`

```python
@dataclass(frozen=True)
class ScenarioEvent:
    params: Dict   # mutable — frozen=True only blocks reassignment, not mutation
```

`event.params["x"] = 1` succeeds silently, violating the immutability contract stated in the module docstring.

**Fix:** Wrap on construction: `params=types.MappingProxyType(dict(item.get("params") or {}))`

---

**M3 — `weather_engine.py`: Immutability claims are false**
File: `src/python/weather_engine.py:86`

Module header states "All public types are immutable frozen dataclasses. No mutation anywhere." `WeatherEngine` is a plain class with a mutable `self._zones` dict and a stateful `self._rng`. `from_states()` directly assigns `engine._zones = dict(states)`. The docstring "tick() returns a new WeatherEngine" is correct but the class is not immutable — it is a stateful manager.

**Fix:** Either remove the immutability claim from the module docstring or refactor `WeatherEngine` to use an immutable mapping for `_zones`.

---

**M4 — `sensor_model.py`: Inconsistent Pd models between active and passive sensors**
File: `src/python/sensor_model.py:226`

`compute_detection_probability()` uses the Nathanson radar range equation for SAR (active) but falls back to the legacy sigmoid-based `compute_pd()` for EO_IR and SIGINT. The two models are not calibrated against each other and can produce significantly different Pd values at similar ranges. SIGINT uses a passive intercept model where range/RCS scaling from `compute_pd()` is physically incorrect.

---

**M5 — `terrain_model.py:compute_dead_zones`: Float accumulation drift in grid loop**
File: `src/python/terrain_model.py:175`

```python
lat = min_lat
while lat <= max_lat + 1e-9:
    lon += grid_resolution  # accumulates fp error across iterations
```

At fine resolutions (`grid_resolution=0.01`) drift accumulates. Use index multiplication instead:
```python
lat = min_lat + i * grid_resolution
```

---

**M6 — `llm_sanitizer.py`: Injection patterns bypassable via unicode homoglyphs**
File: `src/python/llm_sanitizer.py:57`

NFC normalization does not collapse look-alike unicode characters (e.g., Cyrillic `с` vs Latin `c`). An attacker can bypass `"ignore previous instructions"` with homoglyph substitution.

**Fix:** Use NFKC normalization instead of NFC:
```python
normalized = unicodedata.normalize("NFKC", text)
```

---

### LOW

**L1 — `scenario_engine.py`: Uses deprecated `typing.Dict/List/Tuple` aliases**
File: `src/python/scenario_engine.py:27`

All other Wave 5 files use built-in generics (`dict`, `list`, `tuple`) with `from __future__ import annotations`. `scenario_engine.py` imports `Dict`, `List`, `Tuple` from `typing` unnecessarily.

---

**L2 — `weather_engine.py`: Same deprecated `typing` imports**
File: `src/python/weather_engine.py:17` — uses `Dict`, `Optional` from `typing`.

---

**L3 — `checkpoint.py`: No structural validation of `state` content**
File: `src/python/checkpoint.py:72`

`load_checkpoint` validates version and key presence but not `state` structure. A malformed `state` dict will pass validation and fail later with an opaque error. Minimal check: `state` must be a dict with `uavs` and `targets` keys.

---

**L4 — `jammer_model.py`: `contributing_jammer_ids` typed as bare `tuple`**
File: `src/python/jammer_model.py:48`

```python
contributing_jammer_ids: tuple  # should be tuple[int, ...]
```

---

**L5 — `uav_logistics.py`: `refuel()` does not reset `maintenance_hours`**
File: `src/python/uav_logistics.py:84`

Defensible design, but the function name implies a full base return. If maintenance tracking is intentionally independent of refuelling, a comment to that effect would clarify intent.

---

**L6 — `jammer_model.py`: No test file in Wave 5 diff**

`jammer_model.py` is a new file but no `test_jammer_model.py` appears in the Wave 5 diff. Verify coverage exists from a prior wave or add tests.

---

## Test Quality Assessment

**Overall: Good.** All 323 tests pass in 1.49s.

- `test_checkpoint.py` (398 lines): thorough — happy path, file round-trip, version compatibility, all error branches.
- `test_rbac.py`: JWT round-trip, expiry, wrong-secret rejection, AUTH_DISABLED bypass, permission matrix. Short secrets generate 11 warnings (M1).
- `test_llm_sanitizer.py`: comprehensive injection pattern coverage; verifies legitimate military text is preserved.
- `test_scenario_engine.py`: YAML load, validation errors, player tick, event ordering. Missing test for `params` mutability (M2).
- `test_terrain_model.py`: LOS with multiple features, blocked/clear paths, dead-zone computation.
- `test_weather_engine.py`: state cycle, Pd degradation per sensor type, `from_states` factory.
- `test_radar_range.py`: SNR computation, sigmoid Pd mapping, weather attenuation.
- `test_uav_logistics.py`: fuel depletion, RTB threshold, ammo, refuel.
- `test_sim_controller.py`: pause/resume, speed multiplier, step/consume_step, `should_tick`.
- `test_report_generator.py`: JSON and CSV for all three report types.

**Coverage gaps:** `jammer_model.py` has no test file (L6). No test for `tick(dt_s=0)` in weather engine. No homoglyph bypass test in `test_llm_sanitizer.py` (M6).

---

## Summary

| Severity | Count | Items |
|----------|-------|-------|
| CRITICAL | 0 | — |
| HIGH | 2 | H1 (auth off by default), H2 (weak JWT secret fallback) |
| MEDIUM | 6 | M1–M6 |
| LOW | 6 | L1–L6 |

**Blocking for production:** H1 and H2 must be resolved before any non-dev deployment. H1 means the system ships in full-admin no-auth mode by default — unacceptable for a C2 system. All other findings are non-blocking for continued wave development.

---

## Previous Review (Wave 1A)
**Test Results:** 2 flaky failures / 543 passed (failures non-deterministic — confirmed by re-run)

---

## CRITICAL

*(None found)*

---

## HIGH

### [HIGH] Missing `threat_score` key in serialized coverage_gaps — sort is always a no-op

**File:** `src/python/api_main.py:722` and `src/python/sim_engine.py:796–797`

**Issue:** `_serialize_assessment()` serializes `coverage_gaps` as dicts with only `zone_x`, `zone_y`, `lon`, `lat` keys. `_threat_adaptive_dispatches()` then sorts those dicts by `g.get("threat_score", 0.0)` — a key that is never present. All gaps receive score 0.0 and the sort order is undefined (Python stable sort preserves insertion order, which is arbitrary from `_cluster_targets`). High-threat gaps are never prioritized above low-threat ones. The intended behavior — dispatching UAVs to highest-threat coverage gaps first — is silently broken.

**Fix:** Either include `threat_score` in the serialized coverage gap dict, or compute the threat score from `zone_threat_scores` at sort time inside `_threat_adaptive_dispatches()`.

```python
# In _serialize_assessment(), add threat_score to each gap dict:
"coverage_gaps": [
    {
        "zone_x": g.zone_x,
        "zone_y": g.zone_y,
        "lon": round(g.lon, 4),
        "lat": round(g.lat, 4),
        "threat_score": round(
            result.zone_threat_scores.get((g.zone_x, g.zone_y), 0.0), 3
        ),
    }
    for g in result.coverage_gaps
],
```

---

### [HIGH] State mutation inside `_evaluate_autonomy()` while iterating `pending_transitions`

**File:** `src/python/sim_engine.py:1373–1379`

**Issue:** `list(self.pending_transitions.items())` creates a snapshot copy for safe deletion — that part is correct. However, `del self.pending_transitions[uav_id]` mutates the dict mid-loop over the copied list, which is safe here, but the subsequent `for u in self.uavs.values()` loop at line 1381 can add new entries to `pending_transitions` while the expiry loop has already finished. If a UAV's transition fires and a new transition is immediately added in the same tick, it will sit in `pending_transitions` with an expiry in the past on the next tick. Low probability but a correctness issue under fast simulation (demo_fast mode).

**Fix:** Collect expired entries first, then apply, then run the new-transition loop. The current structure already does this implicitly but is fragile. No code change is strictly necessary, but the loop ordering should be documented.

---

### [HIGH] `subscribe_sensor_feed` action bypasses schema validation and has no type guard on `uav_ids` contents

**File:** `src/python/api_main.py:1374–1379`

**Issue:** `uav_ids` items are stored directly in `client_info["sensor_feed_uav_ids"] = set(uav_ids)` without validating that each element is an integer. A malicious or buggy client sending `["../../etc/passwd", 0]` would store strings in the set. These strings later participate in comparisons like `if sc.get("uav_id") == uav_id` — no crash, but the comparison always fails silently and the sensor feed never delivers. More importantly, there is no upper bound on the list size; a client could send thousands of IDs to bloat the set indefinitely.

**Fix:**
```python
uav_ids = payload.get("uav_ids", [])
if not isinstance(uav_ids, list) or len(uav_ids) > 50:
    await _send_error(websocket, "uav_ids must be a list of up to 50 integers", action)
    return
validated_ids = set()
for uid in uav_ids:
    if not isinstance(uid, int):
        await _send_error(websocket, "Each uav_id must be an integer", action)
        return
    validated_ids.add(uid)
client_info = clients.get(websocket, {})
client_info.setdefault("subscriptions", set()).add("SENSOR_FEED")
client_info["sensor_feed_uav_ids"] = validated_ids
```

---

### [HIGH] `subscribe` action double-checks `isinstance(feeds, list)` redundantly; first check is guarded, second is not used as guard

**File:** `src/python/api_main.py:1336–1347`

**Issue:** Line 1336 correctly validates `if not isinstance(feeds, list)` and returns an error. Line 1345 then re-checks `if isinstance(feeds, list):` as a condition for the assignment block. The second check is always True at that point (because the first check already returned if it was False), but it makes the code appear as if the assignment might not happen, which is misleading and could mask future refactoring bugs if the early return is removed. This is a logic clarity issue, not a crash.

**Fix:** Remove the redundant `if isinstance(feeds, list):` guard on line 1345 — the early return already guarantees it.

---

## MEDIUM

### [MEDIUM] `event_logger._writer_loop` opens file with bare `open()` — no error handling on rotation

**File:** `src/python/event_logger.py:32–43`

**Issue:** The initial `open(log_path, "a")` at line 32 and the rotation `open(log_path, "a")` at line 43 have no exception handling. If the `logs/` directory is not writable (e.g., permissions issue on container start, or disk full), the logger raises `OSError` and the background task dies silently. Subsequent `log_event()` calls continue to enqueue events to `_queue` that will never be drained — eventually causing `asyncio.QueueFull` drops. The `stop_logger()` `await _queue.join()` will then hang indefinitely because `task_done()` is never called on queued items.

**Fix:** Wrap both `open()` calls in try/except, log to stderr on failure, and implement a retry or fallback (e.g., dev/null). Also add a check in `stop_logger()` for a cancelled/dead writer task before calling `_queue.join()`.

---

### [MEDIUM] `event_logger.log_event` silently drops events on `QueueFull` with no observable signal

**File:** `src/python/event_logger.py:62–63`

**Issue:** `except asyncio.QueueFull: pass` — the drop is intentional for sim-loop performance, but there is no counter, no log warning, and no metric. In production it is impossible to know whether events were lost. This violates the rule "Never silently swallow errors."

**Fix:** At minimum, increment a module-level `_dropped_events` counter. Optionally log a warning at most once per second using a throttled logger.

---

### [MEDIUM] `battlespace_assessment._get_xy` has zero-coalescing logic bug for explicit `0.0` values

**File:** `src/python/battlespace_assessment.py:90`

**Issue:**
```python
return (t.get("x") or t.get("lon", 0.0), t.get("y") or t.get("lat", 0.0))
```
The `or` operator treats `0.0` as falsy. If a target has `"x": 0.0` (a valid coordinate — e.g., a target exactly on the prime meridian), this falls through to `t.get("lon", 0.0)`. If both `"x"` and `"lon"` are 0.0 the result is still correct, but if `"x"` is 0.0 and `"lon"` is absent, the result is 0.0 — which happens to be correct. The real danger is `"x": 0.0` with a non-zero `"lon"` key present (shouldn't happen with current serialization, but the logic is fragile).

**Fix:**
```python
x = t["x"] if "x" in t else t.get("lon", 0.0)
y = t["y"] if "y" in t else t.get("lat", 0.0)
return (x, y)
```

---

### [MEDIUM] `sim_engine` assessment zip assumes `state["targets"]` and `sim.targets.values()` are in the same order

**File:** `src/python/api_main.py:748–751`

**Issue:**
```python
for td, t_obj in zip(state["targets"], sim.targets.values()):
    td_copy = dict(td)
    td_copy["position_history"] = list(t_obj.position_history)
```
`state["targets"]` is a list comprehension over `self.targets.values()` in `get_state()`, and `sim.targets.values()` is iterated again here. Both iterate the same `dict`, and in Python 3.7+ dicts maintain insertion order, so the ordering is consistent as long as no targets are added or removed between `get_state()` and the zip. However, if `sim.tick()` destroys a target (state change only — targets are never removed from `self.targets` in the current code) this is safe, but the assumption is implicit and one refactor away from silently attaching the wrong `position_history` to the wrong target dict.

**Fix:** Use `target_id` as the key explicitly:
```python
for td in state["targets"]:
    t_obj = sim.targets.get(td["id"])
    if t_obj is None:
        continue
    td_copy = dict(td)
    td_copy["position_history"] = list(t_obj.position_history)
    targets_with_history.append(td_copy)
```

---

### [MEDIUM] `api_main.post_sitrep` and `_handle_sitrep_query` are identical — duplicated logic

**File:** `src/python/api_main.py:833–866` and `972–1016`

**Issue:** The REST endpoint `POST /api/sitrep` and the WebSocket handler `_handle_sitrep_query` compute the identical narrative/key_threats/recommended_actions logic. Any change to the SITREP format must be made in two places.

**Fix:** Extract the shared logic into a private function `_build_sitrep_payload(query_text: str) -> dict` and call it from both handlers.

---

### [MEDIUM] `_ACTION_SCHEMAS` for `set_coverage_mode` validates `mode` as `str` but `set_coverage_mode` maps to internal `"balanced"/"threat_adaptive"` while `VALID_COVERAGE_MODES` uses UI strings

**File:** `src/python/api_main.py:127` and `1322–1332`

**Issue:** The schema marks `mode` as `str`, which passes. Then the handler validates against `VALID_COVERAGE_MODES` (UI strings like `"OPERATIONAL"`, `"THREAT"`, etc.) and calls `sim.set_coverage_mode(mode)`. But `SimulationModel.set_coverage_mode()` only accepts `"balanced"` or `"threat_adaptive"` — it ignores all other strings. So a client sending `mode: "COVERAGE"` passes validation, receives no error, but the sim silently ignores it. The coverage mode is never changed.

**Fix:** Either translate UI mode strings to internal strings before calling `sim.set_coverage_mode()`, or unify the string namespace so `VALID_COVERAGE_MODES` and `sim.set_coverage_mode()` share the same vocabulary.

---

### [MEDIUM] Flaky tests — two tests fail intermittently under full suite run due to probabilistic sim state

**File:** `src/python/tests/test_sim_integration.py::TestSetEnvironment::test_bad_weather_reduces_detection_rate` and `src/python/tests/test_enemy_uavs.py::TestJammingDetection::test_jamming_enemy_detected_by_sigint`

**Issue:** Both tests pass in isolation but fail ~1 in N full-suite runs. The failures are non-deterministic (confirmed: 2 failures in initial run, 0 in rerun of just those tests). These tests rely on probabilistic detection outcomes without seeding `random`. Over 500+ tests the shared global state or timing makes them occasionally produce different outcomes.

**Fix:** Seed `random` with a fixed value in test setup using `random.seed(42)` in a fixture, or use `unittest.mock.patch` to control `evaluate_detection()` return values directly.

---

### [MEDIUM] `_update_enemy_intercept` sets attribute `_intercept_dwell` via `hasattr` guard rather than initializing in `__init__`

**File:** `src/python/sim_engine.py:1091–1092`

**Issue:**
```python
if not hasattr(u, "_intercept_dwell"):
    u._intercept_dwell = 0.0
```
This is a deferred attribute pattern that bypasses `__init__`. `_intercept_dwell` is not declared in `UAV.__init__`, so type checkers and readers cannot know it exists. It also means any code path that accesses `u._intercept_dwell` without going through `_update_enemy_intercept` first will raise `AttributeError`.

**Fix:** Add `self._intercept_dwell: float = 0.0` to `UAV.__init__` and remove the `hasattr` guard.

---

## LOW

### [LOW] `import time as _time` inside `_evaluate_autonomy()` — unnecessary scoped import

**File:** `src/python/sim_engine.py:1368`

**Issue:** `time` is already imported at the top of the module. The `import time as _time` inside the method body re-imports unnecessarily on every call and shadows the module-level name with a local alias.

**Fix:** Remove the scoped import. Use the module-level `time.monotonic()`.

---

### [LOW] `_writer_loop` opens log file with `open()` in text mode without explicit `encoding`

**File:** `src/python/event_logger.py:32`

**Issue:** `open(log_path, "a")` uses the platform default encoding. On Windows this may be `cp1252` rather than UTF-8. JSONL event data may contain non-ASCII characters (target types, theater names, log messages). This is low risk on Linux/macOS servers but non-portable.

**Fix:** `open(log_path, "a", encoding="utf-8")`.

---

### [LOW] `rotate_logs` uses `glob.glob` and sorts lexicographically by filename — correct only because ISO date format sorts correctly

**File:** `src/python/event_logger.py:94`

**Issue:** The sort relies on `events-YYYY-MM-DD.jsonl` filenames sorting chronologically under string sort order. This is correct for ISO 8601 dates. No actual bug, but the assumption is fragile if the filename format ever changes. A comment explaining this dependency would prevent future breakage.

---

### [LOW] `battlespace_assessment._compute_convex_hull` handles `n == 2` as a special case but Shapely handles it natively

**File:** `src/python/battlespace_assessment.py:313`

**Issue:** The explicit `n == 2` branch returns `(points[0], points[1])`. `MultiPoint([p1, p2]).convex_hull` returns a `LineString`, which is handled by the `geom_type == "LineString"` branch below. The manual branch is not wrong but adds dead code relative to the Shapely path and could diverge if the logic in the Shapely branch changes.

**Fix:** Remove the `n == 2` special case and let it fall through to Shapely.

---

### [LOW] Magic number `0.95` (confidence fade factor) and `0.1` (fade threshold) in sim_engine without named constants

**File:** `src/python/sim_engine.py:969–973`

**Issue:** `t.detection_confidence *= 0.95` and `if t.detection_confidence < 0.1` are magic numbers. They appear twice (once for targets, once for enemy UAV fade) without named constants.

**Fix:** Define `CONFIDENCE_FADE_FACTOR = 0.95` and `CONFIDENCE_FADE_THRESHOLD = 0.1` at module level.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 4     |
| MEDIUM   | 7     |
| LOW      | 5     |

**Verdict: BLOCK** — 4 HIGH issues must be addressed before merge.

Priority order for fixes:
1. `threat_score` missing from serialized coverage_gaps (HIGH — silently broken feature)
2. `set_coverage_mode` string mismatch (HIGH — silently broken feature)  
3. `subscribe_sensor_feed` missing input validation (HIGH — security/robustness)
4. Redundant `isinstance` guard in `subscribe` (HIGH — logic clarity)
5. `position_history` zip ordering assumption (MEDIUM — correctness risk)
6. File open error handling in event_logger (MEDIUM — operational risk)

