# UAV Kinematics Fixes — Wave 6B Review

## Status: COMPLETE — 41/41 tests passing

## Fixes Applied

### HIGH — check_separation O(n²) unbounded
Added `_MAX_POSITIONS = 200` constant. `check_separation` raises `ValueError` if `len(positions) > _MAX_POSITIONS`.

### MEDIUM — dt <= 0 causes inverted constraints
Added `if dt <= 0.0: raise ValueError(...)` at start of `step_kinematics`.

### MEDIUM — NaN/inf propagation in KinematicState
Added `_validate_state(state)` helper checking `math.isfinite` for lat, lon, alt_m, speed_mps, heading_deg. Called at entry of `step_kinematics`, `check_separation` (for each state), and `proportional_navigation`.

### MEDIUM — PN sign ambiguity (CORRECTNESS BUG)
Fixed sign convention on line 402-404. Changed from:
```python
omega_los = (-perp_speed / los_dist_m) if cross >= 0 else (perp_speed / los_dist_m)
```
To:
```python
omega_los = (perp_speed / los_dist_m) if cross >= 0 else (-perp_speed / los_dist_m)
```
Verified: pursuer heading north + target moving east produces eastward correction (~0.77° for target 0.1° north). Stationary target to east → cmd ~92°. Stationary target to west → cmd ~268°. All correct.

### MEDIUM — step_kinematics refactored (was 76 lines)
Extracted three helpers:
- `_update_heading(state, target_heading, dt, constraints) -> float`
- `_update_altitude(state, target_alt, dt, constraints) -> tuple[float, float]`
- `_update_position(lat, lon, speed, heading, dt, wind) -> tuple[float, float]`
`step_kinematics` body is now ~15 lines.

### LOW — nav_gain validation
Added `if nav_gain <= 0: raise ValueError(...)` at start of `proportional_navigation`.

## Test Results
```
41 passed in 0.35s
```
No existing tests required updates — the PN sign fix did not break any tests (existing tests were checking directional correctness and they now pass with the correct sign).
