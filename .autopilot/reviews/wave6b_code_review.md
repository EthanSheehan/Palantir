# Wave 6B Code Review

**Reviewed modules:** sensor_weighting, lost_link, uav_kinematics, corridor_detection
**Reviewer:** Sonnet 4.6
**Date:** 2026-03-26

---

## Summary Table

| Module | File Lines | Immutability | Functions >50 Lines | Error Handling | Tests | Overall |
|--------|-----------|-------------|---------------------|----------------|-------|---------|
| sensor_weighting.py | 243 | PASS | None | Partial FAIL | Excellent | MEDIUM issues |
| lost_link.py | 169 | PASS | None | PASS | Excellent | MEDIUM issues |
| uav_kinematics.py | 415 | PASS | step_kinematics (76 lines) | Partial FAIL | Good | MEDIUM/LOW issues |
| corridor_detection.py | 307 | PASS | detect_corridors (69 lines) | Partial FAIL | Excellent | MEDIUM issues |

---

## CRITICAL Issues

None found.

---

## HIGH Issues

None found.

---

## MEDIUM Issues

### M1 — sensor_weighting.py: `weight_fusion_contributions` ignores target_type, always uses "TRUCK" fallback

**File:** `src/python/sensor_weighting.py:211`

```python
fitness = compute_sensor_fitness(c.sensor_type, weather, time_of_day, "TRUCK")
```

`weight_fusion_contributions` cannot accept a `target_type` parameter because `SensorContribution` doesn't carry it. The function silently falls back to `"TRUCK"` for all contributions, meaning SIGINT contributions against a `C2_NODE` get scored as if the target were a TRUCK — dramatically underweighting SIGINT's advantage against emitters.

**Impact:** SIGINT contributions for high-value emitting targets (C2_NODE, RADAR) are weighted with `target_weight=0.5` instead of `1.0`. This biases the fusion pipeline toward EO/IR and SAR even when SIGINT is the ideal sensor.

**Fix:** Add an optional `target_type: str = "TRUCK"` parameter to `weight_fusion_contributions`, or pass target_type alongside contributions. Since `SensorContribution` is frozen (from `sensor_fusion.py`), the cleanest fix is to add a `target_type_map: dict[int, str] | None = None` parameter that maps `uav_id → target_type`.

---

### M2 — sensor_weighting.py: Unknown sensor type silently returns neutral weights with no log

**File:** `src/python/sensor_weighting.py:172-174`

```python
else:
    # Unknown sensor — neutral weights
    w = t = tgt = 0.5
```

Unknown sensor types are silently assigned `0.5` weights. This is a silent failure — if a new sensor type is added to the system but `sensor_weighting.py` is not updated, its weights will be wrong without any indication. This is especially risky because `recommend_sensor_type` only evaluates the three known types, so a new sensor type would never be recommended.

**Fix:** Log a warning when an unknown sensor type is encountered: `import logging; logging.warning("Unknown sensor type %r — using neutral fitness", sensor_type)`. Alternatively, raise a `ValueError` for strict mode operation.

---

### M3 — uav_kinematics.py: `step_kinematics` function is 76 lines — exceeds 50-line limit

**File:** `src/python/uav_kinematics.py:158-233`

The `step_kinematics` function spans 76 lines, exceeding the project's 50-line function limit from `coding-style.md`. The function has three clearly separable phases: heading/speed update, altitude update, and position update.

**Fix:** Extract helpers:
- `_update_heading_speed(state, target_heading, target_speed, dt, constraints) -> tuple[float, float]`
- `_update_altitude(state, target_alt, dt, constraints) -> tuple[float, float]`
- `_update_position(state, new_speed, new_heading, dt, wind) -> tuple[float, float]`

---

### M4 — uav_kinematics.py: `proportional_navigation` has a sign ambiguity in LOS rotation direction

**File:** `src/python/uav_kinematics.py:402-404`

```python
cross = los_nx * perp_vy - los_ny * perp_vx
omega_los = (-perp_speed / los_dist_m) if cross >= 0 else (perp_speed / los_dist_m)
```

The sign convention for `omega_los` is reversed: when `cross >= 0`, the LOS is rotating counter-clockwise in standard math convention (positive angular velocity). Negating it here means the PN law applies a correction in the wrong direction when the LOS rotates counter-clockwise. The function passes the existing tests because the tests only check rough directional bounds (not precise PN outputs), and the test for a stationary target directly ahead is degenerate (zero LOS rate regardless of sign).

**Impact:** For a crossing target (the main PN use case), the commanded heading correction could be in the wrong direction, causing the pursuer to manoeuvre away from the intercept rather than toward it.

**Fix:** Verify the sign convention using a known PN scenario: pursuer heading north, target moving east and slightly north — the pursuer should lead the target by turning east. The current sign would cause the pursuer to turn west. Correct to:
```python
omega_los = (perp_speed / los_dist_m) if cross >= 0 else (-perp_speed / los_dist_m)
```

---

### M5 — corridor_detection.py: `_heading_deg` uses `atan2(dy, dx)` — wrong axis order for geographic bearing

**File:** `src/python/corridor_detection.py:103-108`

```python
def _heading_deg(p1, p2) -> float:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.degrees(math.atan2(dy, dx)) % 360.0
    return angle
```

The coordinate convention in `corridor_detection.py` uses `(lon, lat)` tuples (confirmed by `_extract_points` at line 296-298 and `_make_history` in the test at line 127). For geographic bearing, north is the positive `lat` direction (y-axis), and east is the positive `lon` direction (x-axis). The correct bearing formula is `atan2(dx, dy)` (east component over north component), not `atan2(dy, dx)`. The current formula computes a math angle (measured counter-clockwise from east), not a compass bearing (measured clockwise from north), meaning `heading_deg` in the `Corridor` output is off by a 90° rotation and handedness inversion.

**Impact:** The `Corridor.heading_deg` field is systematically incorrect for any non-axis-aligned path. A target moving east (bearing 90°) would be reported as heading 0° (north). Callers using this field for threat direction assessment would receive wrong data.

**Fix:**
```python
angle = math.degrees(math.atan2(dx, dy)) % 360.0  # atan2(east, north) = compass bearing
```

---

### M6 — corridor_detection.py: `detect_corridors` function is 69 lines — exceeds 50-line limit

**File:** `src/python/corridor_detection.py:187-256`

`detect_corridors` is 69 lines. It has a clear extraction point: the per-target pipeline (extract → simplify → score → build Corridor) can be extracted into `_process_target(target_id, history, epsilon_deg, min_consistency) -> Corridor | None`.

**Fix:** Extract `_process_target` helper to bring `detect_corridors` under 50 lines.

---

## LOW Issues

### L1 — lost_link.py: `LinkState.configs` and `LinkState.statuses` typed as `dict` not `dict[str, ...]`

**File:** `src/python/lost_link.py:54-55`

```python
configs: dict  # drone_id -> LinkConfig
statuses: dict  # drone_id -> LinkStatus
```

Both fields are annotated as bare `dict` rather than `dict[str, LinkConfig]` / `dict[str, LinkStatus]`. This loses type-checker enforcement; callers cannot rely on static analysis to catch incorrect key/value usage. The intent is documented in comments but not enforced.

**Fix:**
```python
configs: dict[str, LinkConfig]
statuses: dict[str, LinkStatus]
```

---

### L2 — lost_link.py: `SAFE_LAND` behavior maps to `"RTB"` mode — semantic mismatch

**File:** `src/python/lost_link.py:153-155`

```python
_BEHAVIOR_MODE_MAP: dict[LostLinkBehavior, Optional[str]] = {
    LostLinkBehavior.LOITER: "SEARCH",
    LostLinkBehavior.RTB: "RTB",
    LostLinkBehavior.SAFE_LAND: "RTB",  # <-- same as RTB
    LostLinkBehavior.CONTINUE: None,
}
```

`SAFE_LAND` and `RTB` both map to `"RTB"` mode. The distinction between "fly home to base" and "land immediately at nearest safe location" is lost. The test at line 419 accepts either `"RTB"` or `"SAFE_LAND"`, acknowledging this ambiguity. If the sim has a separate `SAFE_LAND` mode or this maps to physical behavior, this is a semantic bug.

**Recommendation:** If the simulation engine has a distinct `SAFE_LAND` mode, map to it. If not, add a comment explaining why both use `RTB`: `# SAFE_LAND: sim has no dedicated land-in-place mode; RTB is the safest available behavior`.

---

### L3 — uav_kinematics.py: `step_kinematics` speed update is instantaneous — comment says "rate-limit can be added" but no guard

**File:** `src/python/uav_kinematics.py:188-189`

```python
# --- Speed update (instantaneous for simplicity; rate-limit can be added) ---
new_speed = max(constraints.min_speed_mps, min(constraints.max_speed_mps, target_speed))
```

Speed changes are instantaneous — a UAV can jump from 55 m/s to 110 m/s in a single tick. This is physically unrealistic and inconsistent with the rate-limited heading and altitude updates. The comment acknowledges this but leaves it as a known gap.

**Recommendation:** Acceptable as-is for the current simulation fidelity, but the comment should note the acceleration rate that would be needed (e.g., `# TODO: add speed_rate_mps2 to UAVConstraints for realistic acceleration`).

---

### L4 — uav_kinematics.py: `check_separation` is O(N²) — should be documented

**File:** `src/python/uav_kinematics.py:241-261`

The separation check iterates all N² pairs. At the current sim scale (≤10 UAVs), this is not a bottleneck, but the complexity is undocumented. Add a comment: `# O(N²) — acceptable for small fleets (N ≤ 20); use spatial index for larger swarms`.

---

### L5 — corridor_detection.py: `_compute_speed_kmh` uses simplified isotropic `_KM_PER_DEG` for both lat and lon

**File:** `src/python/corridor_detection.py:171-172`

```python
dx = (points[i][0] - points[i - 1][0]) * _KM_PER_DEG
dy = (points[i][1] - points[i - 1][1]) * _KM_PER_DEG
```

The same `_KM_PER_DEG` constant (111 km/deg) is used for both longitude (`dx`) and latitude (`dy`) differences. Longitude degrees are shorter than latitude degrees at non-equatorial latitudes (`lon_km = lat_km * cos(lat)`). At 45° latitude, longitude distances are ~78 km/deg, so the east-west speed component is overestimated by ~42%. The `_heading_deg` helper in the same file ignores the same correction, making the error consistent but the absolute speed incorrect.

**Fix:** Apply a `cos(lat)` correction for longitude distances, using the mean latitude of the path. This matches the approach used in `uav_kinematics.py`'s `_horiz_dist_m`. Alternatively, note the limitation in the docstring: `# Isotropic approximation — speed values may be inaccurate far from the equator`.

---

### L6 — sensor_weighting.py: `_sigint_target_weight` has unreachable branch for MANPADS

**File:** `src/python/sensor_weighting.py:122-128`

```python
def _sigint_target_weight(target_type: str) -> float:
    if target_type in _EMITTING_TARGETS:
        return 1.0
    if target_type in _SMALL_RCS_TARGETS or target_type == "MANPADS":
        return 0.35
    return 0.5
```

`_SMALL_RCS_TARGETS` is defined as `frozenset({"MANPADS", "ENEMY_UAV"})` (line 33), so `target_type == "MANPADS"` is always already covered by `target_type in _SMALL_RCS_TARGETS`. The `or target_type == "MANPADS"` branch is dead code.

**Fix:** Remove the redundant `or target_type == "MANPADS"` clause.

---

## Test Quality Assessment

| File | Test Count | Coverage | Quality |
|------|-----------|----------|---------|
| test_sensor_weighting.py | 25 | High | Good — covers all three sensor types and weather/time/target axes |
| test_lost_link.py | 45 | Very High | Excellent — comprehensive state-machine coverage including edge cases |
| test_uav_kinematics.py | 30 | High | Good — covers all six functions; PN tests are weak |
| test_corridor_detection.py | 28 | High | Good — covers DP simplification, consistency, and detect/attribute pipeline |

**Notable test issues:**

- `test_uav_kinematics.py:361-376` — `test_nav_gain_scales_output` only asserts both results are floats and in bounds — it does not assert that different gains produce different outputs. The test is vacuous. The `test_heading_toward_target_to_east` test is meaningful but the M4 sign bug means this test passes for the wrong reason (stationary targets have zero LOS rate, so sign doesn't matter).
- `test_sensor_weighting.py:246-251` — `test_recommend_eo_ir_clear_day` has a redundant double assertion: `assert rec in ("EO_IR", "SAR", "SIGINT")` followed immediately by `assert rec == "EO_IR"`. The first assertion is subsumed by the second.
- `test_uav_kinematics.py:314-318` — `test_offset_bounded` asserts `offset` is in `[-180, 180]` but the implementation clamps to `[-90, 90]`. The test is under-constrained and would pass even if the clamp were removed.
- `test_corridor_detection.py:95-99` — `test_random_walk_low_consistency` uses a back-and-forth path that produces identical forward and reverse bearings via circular mean, giving artificially zero mean deviation — the test may pass for the wrong reason. A truly random walk with stochastic jitter would be more robust.

---

## Action Items (Priority Order)

1. **[MEDIUM]** Fix `_heading_deg` axis order bug: `atan2(dy, dx)` → `atan2(dx, dy)` — `corridor_detection.py:107`
2. **[MEDIUM]** Verify and fix PN sign convention for `omega_los` — `uav_kinematics.py:404`
3. **[MEDIUM]** Add `target_type` parameter to `weight_fusion_contributions` to fix TRUCK fallback — `sensor_weighting.py:211`
4. **[MEDIUM]** Add warning log for unknown sensor types in `compute_sensor_fitness` — `sensor_weighting.py:172`
5. **[MEDIUM]** Extract helpers from `step_kinematics` to bring it under 50 lines — `uav_kinematics.py:158`
6. **[MEDIUM]** Extract `_process_target` from `detect_corridors` to bring it under 50 lines — `corridor_detection.py:187`
7. **[LOW]** Add typed annotations `dict[str, LinkConfig]` / `dict[str, LinkStatus]` to `LinkState` — `lost_link.py:54`
8. **[LOW]** Clarify or fix `SAFE_LAND` → `"RTB"` mode mapping — `lost_link.py:154`
9. **[LOW]** Remove dead code `or target_type == "MANPADS"` in `_sigint_target_weight` — `sensor_weighting.py:127`
10. **[LOW]** Apply `cos(lat)` correction to `_compute_speed_kmh` or document limitation — `corridor_detection.py:171`
11. **[LOW]** Document O(N²) complexity in `check_separation` — `uav_kinematics.py:241`
12. **[LOW]** Strengthen `test_nav_gain_scales_output` to assert outputs differ — `test_uav_kinematics.py:361`
