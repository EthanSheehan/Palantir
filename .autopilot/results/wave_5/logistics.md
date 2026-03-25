# W5-004: Logistics Module — Result

**Status: PASS**

## Files Created
- `src/python/uav_logistics.py` — UAVLogistics frozen dataclass + pure functions
- `src/python/tests/test_uav_logistics.py` — 29 tests, all passing

## Files Modified
- `src/python/sim_engine.py` — integrated logistics into tick loop, get_state, swarm filtering

## Acceptance Criteria
- [x] `UAVLogistics` frozen dataclass: fuel_pct (0–1.0), ammo count, maintenance_hours
- [x] Fuel depletes by mode/speed — IDLE < SEARCH < FOLLOW < PAINT < INTERCEPT
- [x] Fuel below 20% threshold triggers automatic RTB (mode set to "RTB")
- [x] Swarm coordinator filters assignments by fuel availability (needs_rtb check)
- [x] Theater YAML base_location used for RTB — already in blue_force.uavs (base_lon/base_lat)
- [x] `get_state()` includes logistics dict per drone (fuel_pct, ammo, maintenance_hours, needs_rtb)

## Test Results
```
29 passed in 0.60s
```

## Pre-existing Failure (not caused by this feature)
- `test_enemy_uavs.py::TestJammingDetection::test_jamming_enemy_detected_by_sigint` — confirmed failing before this PR on base commit ad9b42c
