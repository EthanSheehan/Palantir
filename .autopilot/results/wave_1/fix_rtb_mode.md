# W1-022: Fix RTB Mode — Results

**Status:** PASS

## What Was Done

### TDD Protocol Followed
1. Tests written first in `src/python/tests/test_rtb_navigation.py` — 11 tests, 4 classes
2. Tests run RED (8 failed, 3 passed — confirming no implementation yet)
3. Implementation added to `src/python/sim_engine.py`
4. Tests run GREEN (11/11 passed)
5. Full suite run: **540 passed, 0 failed**

### Files Modified

**`src/python/sim_engine.py`**
- Added `ARRIVAL_THRESHOLD_KM = 0.5` constant (line ~99)
- Added `self.home_position: Tuple[float, float] = (x, y)` to `UAV.__init__` — defaults to spawn position
- Replaced RTB drift placeholder (3 lines) with real navigation using `_turn_toward()`:
  - Computes bearing to `home_position` each tick
  - Checks arrival (`dist_deg < ARRIVAL_THRESHOLD_KM * DEG_PER_KM`)
  - Transitions to IDLE on arrival, zeroes velocity
  - Post-move arrival re-check handles overshoot
- In `SimulationModel.initialize()`: sets `uav.home_position` from `theater.blue_force.uavs.base_lon/base_lat` when theater config present

**`src/python/tests/test_rtb_navigation.py`** (new file)
- 11 tests across 4 classes covering all plan requirements

### No Theater YAML Changes Needed
`base_lon` and `base_lat` were already present in all 3 theater YAMLs (romania, south_china_sea, baltic) and already parsed in `theater_loader.py`.

## Test Results

```
src/python/tests/test_rtb_navigation.py — 11 passed
Full suite — 540 passed, 0 failed
```

## Verification Checklist
- [x] Drones in RTB mode navigate to home and transition to IDLE
- [x] No "drift slowly" placeholder remains
- [x] All existing tests pass (540 total)
- [x] `home_position` stored as tuple, defaults to spawn, overridden by theater config
- [x] `_turn_toward()` used for smooth heading changes
- [x] `ARRIVAL_THRESHOLD_KM` constant defined
