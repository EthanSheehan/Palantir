# W6-027: 3-DOF UAV Kinematics Upgrade

## Status: COMPLETE

## Deliverables

### New module: `src/python/uav_kinematics.py`

Immutable, pure-function 3-DOF kinematic library. Uses only `math` stdlib.

**Types (all frozen dataclasses):**
- `KinematicState` — lat, lon, alt_m, speed_mps, heading_deg, climb_rate_mps
- `WindVector` — speed_mps, direction_deg (meteorological FROM convention)
- `UAVConstraints` — max/min speed, turn rate, climb rate, altitude limits, min separation
- `DEFAULT_CONSTRAINTS` — MQ-9 Reaper class (110 m/s max, 3 dps turn, 15 m/s climb, 300–15000m)

**Functions:**
- `apply_wind(state, wind) -> (ground_speed_mps, track_deg)` — vector addition of airspeed + wind velocity; returns ground speed and track angle
- `step_kinematics(state, target_heading, target_alt, target_speed, dt, constraints, wind) -> KinematicState` — one-tick advance; rate-limited heading/altitude/speed changes; optional wind displacement
- `check_separation(positions, min_sep_m) -> list[tuple[int,int]]` — all (i,j) pairs with horizontal separation < min_sep_m
- `avoid_collision(state, threats, min_sep_m) -> float` — repulsion-weighted heading offset (±90° clamped); collocated threat handled via 90° right escape
- `proportional_navigation(pursuer, target_lat, target_lon, target_speed, target_heading, nav_gain=3.0) -> float` — PN guidance law returning commanded heading [0,360)

### New test file: `src/python/tests/test_uav_kinematics.py`

41 tests across 7 test classes:
- `TestKinematicState` — frozen, field access
- `TestWindVector` — frozen, field access
- `TestUAVConstraints` — sensible defaults, frozen
- `TestApplyWind` — no wind, tailwind, headwind, crosswind, return type
- `TestStepKinematics` — returns new state, position advances, turn rate limit, altitude clamp min/max, climb rate limit, speed clamp min/max, wind applied, None wind
- `TestCheckSeparation` — far apart, same position, close positions, below threshold, single UAV, empty list, multiple violations, sorted index pairs
- `TestAvoidCollision` — no threats, nearby threat, return type, far threat, offset bounded
- `TestProportionalNavigation` — returns float, target ahead, target east, target west, collocated, nav gain effect, output in degrees

## Test Results

```
41 passed in 0.81s
```

Full suite: 1762 passed, 26 failed (pre-existing failures only — none introduced).

## Design Notes

- All state is immutable; every function returns a new object.
- Wind uses meteorological convention (direction wind blows FROM).
- PN guidance: LOS bearing + N*Vc*omega_los correction; degenerate range handled gracefully.
- Collision avoidance: collocated UAVs escape 90° right; proximity weighted.
- No external dependencies — pure `math` stdlib as required.
