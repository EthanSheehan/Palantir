# W6-034: Vision Simulator Fixes

## Status: COMPLETE

## Bugs Fixed

### 1. TrackingScenario.update_drone() — drone never chased targets
**File:** `src/python/vision/video_simulator.py`

The body was a `pass` stub. Replaced with real chase logic:
- Calculates bearing from drone to target using `_calculate_bearing_deg()`
- Calculates range using `_calculate_range_m()`
- Updates `drone["yaw"]` to face target
- Moves drone at `drone["speed"]` m/s toward target per tick
- Caps step distance to remaining range to prevent overshoot
- No-ops gracefully when range < 1m or target_id not found in blocks

### 2. vision_processor.py — hardcoded Bristol coordinates
**File:** `src/python/vision/vision_processor.py`

Replaced hardcoded `{"lat": 51.4545, "lon": -2.5879, ...}` with neutral defaults `{"lat": 0.0, "lon": 0.0, ...}` and added `update_telemetry(telemetry: dict)` method that accepts real drone state from MAVLink/sim_engine and updates only the keys present in the dict.

## Tests Written
**File:** `src/python/tests/test_vision_fixes.py` — 9 tests, all pass

### TrackingScenario tests (5)
- `test_drone_moves_toward_target` — haversine distance decreases after tick
- `test_drone_lat_lon_change_after_tick` — lat/lon must change
- `test_no_crash_when_target_missing` — no exception when target absent
- `test_drone_does_not_overshoot_nearby_target` — step capped at range
- `test_yaw_updated_to_face_target` — yaw set to bearing

### VisionProcessor telemetry tests (4)
- `test_update_telemetry_full` — all fields updated
- `test_update_telemetry_partial` — only provided keys updated
- `test_update_telemetry_replaces_bristol` — Bristol coords gone after update
- `test_update_telemetry_method_exists` — method exists on class

## Test Suite Results
- New tests: 9/9 pass
- Full suite: 1788 passed, 0 failed
