# Wave 6B Security Review

Reviewed: 2026-03-26
Modules: sensor_weighting.py, lost_link.py, uav_kinematics.py, corridor_detection.py

---

## Summary Table

| Module | CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| sensor_weighting.py | 0 | 0 | 2 | 1 |
| lost_link.py | 0 | 0 | 1 | 1 |
| uav_kinematics.py | 0 | 1 | 2 | 1 |
| corridor_detection.py | 0 | 0 | 3 | 1 |

**Total: 0 CRITICAL, 1 HIGH, 8 MEDIUM, 4 LOW**

---

## sensor_weighting.py

### MEDIUM — `time_of_day` accepts NaN/inf, silently corrupting all EO/IR calculations
**Location:** `_eo_ir_time_weight()`, line 75
```python
hours_from_noon = abs(time_of_day - 12.0)
```
If `time_of_day` is `float('nan')` or `float('inf')`, `abs(nan - 12.0)` propagates NaN through `math.cos()`, which returns NaN. The `_clamp()` call `max(0.35 + NaN * 0.65)` then silently returns NaN because NaN comparisons always return False in `min`/`max`. This NaN propagates into `combined_weight` and ultimately into fusion confidence scores.

`_sar_time_weight` and `_sigint_time_weight` ignore the parameter, so only EO/IR is affected — but it is the most commonly used sensor type.

**Fix:** Validate at `compute_sensor_fitness()` entry:
```python
if not math.isfinite(time_of_day) or not (0.0 <= time_of_day < 24.0):
    raise ValueError(f"time_of_day must be in [0, 24); got {time_of_day!r}")
```

---

### MEDIUM — `weather["intensity"]` is cast to float without NaN/range guard
**Location:** `_eo_ir_weather_weight()` line 60, `_sar_weather_weight()` line 93
```python
intensity = float(weather.get("intensity", 0.0))
```
`float()` converts `"nan"` (string) to `float('nan')`, and accepts values outside [0, 1] silently. An intensity of 2.0 produces `base = 1.0 - 0.85 * 2.0 = -0.7`, which `_clamp()` correctly clips to 0.0. However NaN bypasses the clamp and propagates: `max(0.0, NaN)` returns NaN.

**Fix:** After the cast, validate:
```python
intensity = float(weather.get("intensity", 0.0))
if not math.isfinite(intensity):
    intensity = 0.0
intensity = max(0.0, min(1.0, intensity))
```

---

### LOW — `weight_fusion_contributions()` always uses "TRUCK" as target_type
**Location:** `weight_fusion_contributions()`, line 211
```python
fitness = compute_sensor_fitness(c.sensor_type, weather, time_of_day, "TRUCK")
```
The function has no `target_type` parameter, so all contributions are weighted as if every target is a TRUCK, ignoring SIGINT's domain advantage for C2_NODE/RADAR targets (weight difference: 0.5 vs 1.0). This is a logical correctness issue that degrades fusion quality for emitting targets. Not a safety hazard, but the hardcoded fallback should be documented or the API should accept `target_type`.

**Fix:** Add `target_type: str = "TRUCK"` parameter so callers can pass the actual target type.

---

## lost_link.py

### MEDIUM — Negative `current_tick` produces nonsensical `ticks_since_contact` with no guard
**Location:** `check_link_status()`, line 140
```python
ticks_since = current_tick - existing.last_contact_tick
is_lost = ticks_since >= config.timeout_ticks
```
If `current_tick` is negative or less than `last_contact_tick` (e.g., clock reset, integer wrap, or a caller passing invalid data), `ticks_since` becomes negative. A negative value never satisfies `>= config.timeout_ticks` (default 30), so the link is permanently reported as healthy even after a genuine outage. This is a silent safety degradation: lost-link failsafe would never trigger.

**Fix:** Clamp at the earliest safe value:
```python
ticks_since = max(0, current_tick - existing.last_contact_tick)
```
And validate `current_tick >= 0` at entry, or at minimum document the expected range.

---

### LOW — `timeout_ticks=0` immediately triggers lost-link on every tick
**Location:** `configure_drone()`, line 92; `LinkConfig`, line 40
```python
@dataclass(frozen=True)
class LinkConfig:
    timeout_ticks: int = 30
```
Nothing prevents `timeout_ticks=0` or negative values. With `timeout_ticks=0`, `is_lost = ticks_since >= 0` is always True (since `ticks_since >= 0` always), triggering failsafe actions on every tick for that drone. With a negative value the condition is vacuously always True. In a MANUAL autonomy mode this would cause unexpected mode transitions.

**Fix:** Validate in `configure_drone()`:
```python
if timeout_ticks < 1:
    raise ValueError(f"timeout_ticks must be >= 1; got {timeout_ticks}")
```

---

## uav_kinematics.py

### HIGH — `check_separation()` is O(n²) with no input size limit (resource exhaustion)
**Location:** `check_separation()`, lines 250–261
```python
n = len(positions)
for i in range(n):
    for j in range(i + 1, n):
        dist = _horiz_dist_m(...)
```
The nested loop is O(n²) `_horiz_dist_m` calls (each involving `math.cos`, `math.radians`, `math.hypot`). There is no cap on `len(positions)`. If a buggy caller passes all targets plus all drones plus all waypoints as `KinematicState` objects, a list of 500 items runs 125,000 trig calls synchronously on the 10 Hz simulation tick thread, blocking all WebSocket clients for hundreds of milliseconds.

This mirrors the same pattern flagged as HIGH in dbscan_clustering.py.

**Fix:** Add a guard at function entry:
```python
_MAX_POSITIONS = 200
if len(positions) > _MAX_POSITIONS:
    raise ValueError(f"check_separation: positions list exceeds {_MAX_POSITIONS} entries")
```

---

### MEDIUM — `dt <= 0` causes division by zero in `new_climb_rate` computation
**Location:** `step_kinematics()`, line 197
```python
new_climb_rate = clamped_alt_change / dt if dt > 1e-9 else 0.0
```
The `dt > 1e-9` guard here is correct. However, `max_alt_change = constraints.max_climb_rate_mps * dt` on line 193 with `dt=0` produces `max_alt_change=0.0`, meaning all `clamped_alt_change` values are also 0.0. The guard correctly handles this path. But if `dt` is negative (e.g., a time-reversal bug upstream), `max_alt_change` becomes negative, `max(-max_alt_change, min(max_alt_change, alt_error))` inverts the clamp logic, and the UAV can teleport altitude. `max_delta` for heading similarly inverts.

**Fix:** Validate `dt > 0` at entry:
```python
if dt <= 0.0:
    raise ValueError(f"dt must be positive; got {dt}")
```

---

### MEDIUM — NaN/inf in `KinematicState` positions silently propagates through all calculations
**Location:** `step_kinematics()`, `apply_wind()`, `avoid_collision()`, `proportional_navigation()`
None of the public functions validate that `state.lat`, `state.lon`, `state.speed_mps`, or `state.heading_deg` are finite. A `KinematicState` with `lat=float('nan')` propagates NaN through `_horiz_dist_m` (returns NaN), through `math.cos(math.radians(NaN))` (returns NaN), and ultimately produces a new `KinematicState` with NaN positions. The simulation continues silently with a drone at NaN coordinates.

`proportional_navigation()` has a guard at `los_dist_m < 1e-3` but `math.hypot(NaN, NaN)` returns NaN which is not `< 1e-3`, bypassing the guard and proceeding to produce NaN headings.

**Fix:** Add a finite-check helper and call it in `step_kinematics` and `check_separation` entry:
```python
def _validate_state(state: KinematicState) -> None:
    if not all(math.isfinite(v) for v in (state.lat, state.lon, state.alt_m, state.speed_mps)):
        raise ValueError(f"KinematicState contains non-finite values: {state}")
```

---

### LOW — `nav_gain` of 0 or negative inverts PN guidance output
**Location:** `proportional_navigation()`, line 409
```python
a_cmd_dps = nav_gain * vc * math.degrees(omega_los) / max(pursuer.speed_mps, 1.0)
```
`nav_gain=0.0` causes the commanded heading to equal the LOS bearing (no PN correction — pure pursuit only). `nav_gain < 0` inverts the correction, causing the pursuer to steer away from the target. Neither case raises an error. Typical PN gains are 3–5; there is no validation.

**Fix:** Validate `nav_gain > 0` or document the expected range. A reasonable guard: `if nav_gain <= 0: raise ValueError(...)`.

---

## corridor_detection.py

### MEDIUM — `douglas_peucker()` is unboundedly recursive on large inputs (stack overflow)
**Location:** `douglas_peucker()`, lines 90–91
```python
left = douglas_peucker(points[: max_idx + 1], epsilon)
right = douglas_peucker(points[max_idx:], epsilon)
```
This is a divide-and-conquer recursion. In the pathological case (sorted data or nearly-linear paths where `max_idx` always falls at index 1 or n-2), the recursion depth equals `len(points) - 1`. With no input size limit, a target history of 1000 points can cause recursion depth of ~999. Python's default limit is 1000, so this will raise `RecursionError` in practice for histories that are nearly-straight lines (common for vehicles driving roads).

**Fix:** Add an input size cap in `detect_corridors()`:
```python
_MAX_HISTORY_POINTS = 500
points = points[:_MAX_HISTORY_POINTS]
```
And/or convert the recursion to an iterative stack implementation.

---

### MEDIUM — `_extract_points()` silently defaults missing lat/lon to `(0.0, 0.0)`
**Location:** `_extract_points()`, line 296
```python
lon = entry.get("lon", entry.get("x", 0.0))
lat = entry.get("lat", entry.get("y", 0.0))
```
If a history entry is missing both `lon`/`x` and `lat`/`y`, the point falls back to `(0.0, 0.0)` (null island, off the coast of Africa). This false point will be included in the path, corrupting the Douglas-Peucker simplification and heading consistency calculation. The corridor may then be incorrectly detected or rejected.

Additionally, `float(lon)` and `float(lat)` on line 298 will raise `TypeError` if the values are not numeric (e.g., `None` or a string that isn't a valid float), propagating an unhandled exception up through `detect_corridors()`.

**Fix:**
```python
try:
    lon = float(entry.get("lon", entry.get("x")))
    lat = float(entry.get("lat", entry.get("y")))
    if not math.isfinite(lon) or not math.isfinite(lat):
        continue
except (TypeError, ValueError):
    continue
pts.append((lon, lat))
```

---

### MEDIUM — `target_histories` dict is unbounded; large inputs cause O(n) recursive work per target
**Location:** `detect_corridors()`, line 215
```python
for target_id, history in target_histories.items():
```
There is no cap on the number of targets or on `len(history)` per target. Each target runs `douglas_peucker()` (potentially deep recursion as above), `compute_heading_consistency()` (O(n) trig), and `_compute_speed_kmh()` (O(n)). With 1000 targets, each with 500 history points, this is 500,000 total point operations synchronously on the simulation tick.

**Fix:** Add a cap on the number of targets processed per call:
```python
_MAX_TARGETS = 200
_MAX_HISTORY = 200
items = list(target_histories.items())[:_MAX_TARGETS]
for target_id, history in items:
    history = history[:_MAX_HISTORY]
```

---

### LOW — `corridor_id` is derived directly from `target_id` without sanitization
**Location:** `detect_corridors()`, line 239
```python
corridor_id = f"COR-{target_id}"
```
If `target_id` contains path separators, newlines, or control characters (e.g., from a scenario script injecting malformed target IDs), these propagate directly into `corridor_id`. If `corridor_id` is later used in a file path, log entry, or UI display without escaping, this could enable path traversal or log injection. Low risk in the current code paths but worth sanitizing at the source.

**Fix:** Sanitize the ID: `corridor_id = f"COR-{re.sub(r'[^A-Za-z0-9_-]', '_', target_id)}"`.

---

## Priority Fix Order

1. **HIGH — uav_kinematics check_separation O(n²) unbounded**: Add input size cap before next load test
2. **MEDIUM — corridor_detection douglas_peucker unbounded recursion**: Cap history input + consider iterative rewrite
3. **MEDIUM — corridor_detection _extract_points null-island fallback**: Add validation + skip invalid entries
4. **MEDIUM — corridor_detection target_histories unbounded**: Cap target count and history length per target
5. **MEDIUM — uav_kinematics negative dt inverts constraints**: Validate dt > 0 at step_kinematics entry
6. **MEDIUM — uav_kinematics NaN state propagation**: Add finite-value guard on KinematicState entry points
7. **MEDIUM — sensor_weighting time_of_day NaN propagation**: Validate finite + range at compute_sensor_fitness entry
8. **MEDIUM — sensor_weighting weather intensity NaN bypass**: Guard float cast + clamp intensity to [0, 1]
9. **MEDIUM — lost_link negative current_tick disables failsafe**: Clamp ticks_since to >= 0
10. **LOW — uav_kinematics nav_gain=0 inverts guidance**: Validate nav_gain > 0
11. **LOW — lost_link timeout_ticks=0 always fires failsafe**: Validate timeout_ticks >= 1
12. **LOW — sensor_weighting hardcoded TRUCK fallback**: Add target_type parameter to weight_fusion_contributions
13. **LOW — corridor_detection target_id injection into corridor_id**: Sanitize target_id before interpolation
