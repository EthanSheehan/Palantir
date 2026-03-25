# W3-003: Sensor Fusion Upgrade with FilterPy Kalman Tracks

## Status: COMPLETE

## Changes Made

### 1. `requirements.txt`
- Added `filterpy>=1.4.5`

### 2. `src/python/sensor_fusion.py`
- Added `KalmanTrackState` frozen dataclass (target_id, position_estimate, position_covariance, velocity_estimate, last_update_time)
- Added `KalmanTracker` class using `filterpy.kalman.UnscentedKalmanFilter` with constant-velocity model (4-state: lat, lon, vlat, vlon)
  - `update()` — averages valid measurements, runs UKF predict+update cycle
  - `predict()` — forward prediction with dt
  - `get_track()` — returns current track state or None
  - `remove_track()` — removes track and associated filter
- Added optional `lat`/`lon` fields to `SensorContribution` (default None, backward compatible)
- Added optional `position_estimate`, `position_covariance`, `disagreement` fields to `FusedDetection` (default None/False, backward compatible)
- Added temporal decay: contributions older than 30s get confidence halved
- Added cross-sensor disagreement detection: if sensor-type centroids differ by >500m, `disagreement=True`
- `fuse_detections()` now accepts optional `current_time` parameter for temporal decay (default None = no decay, fully backward compatible)
- NaN/Inf measurements are rejected by KalmanTracker

### 3. `src/python/tests/test_kalman_fusion.py` — 25 new tests
- KalmanTrackState: frozen, fields
- KalmanTracker: init, no tracks, single update, multiple updates reduce covariance, multi-sensor, realistic data, predict forward, predict nonexistent, remove, remove nonexistent
- Temporal decay: stale reduced, no decay within threshold
- Cross-sensor disagreement: flagged when >500m apart, not flagged when close, not flagged for single type
- FusedDetection new fields: optional position_estimate/covariance, disagreement default
- Empty/bad measurements: empty returns None, NaN rejected, Inf rejected
- Backward compatibility: fuse_detections without current_time, SensorContribution without lat/lon

## Test Results
- 25/25 new tests: PASS
- 13/13 existing sensor_fusion tests: PASS
- Full suite: 1 pre-existing failure (test_hungarian_swarm), 5 pre-existing errors (test_mission_store) — unrelated to this change
