# W6-037: Magic Constants into Grid-SentinelSettings

## Status: COMPLETE

## Changes Made

### `src/python/config.py`
Added 10 new fields to `Grid-SentinelSettings` (all env-var overridable via Pydantic):

| Field | Default | Env Var | Source constant |
|---|---|---|---|
| `autopilot_scan_delay` | `2.0` | `AUTOPILOT_SCAN_DELAY` | `autopilot.py:101` `asyncio.sleep(2.0)` |
| `autopilot_authorize_delay` | `5.0` | `AUTOPILOT_AUTHORIZE_DELAY` | `autopilot.DEFAULT_APPROVAL_DELAY` |
| `autopilot_follow_delay` | `4.0` | `AUTOPILOT_FOLLOW_DELAY` | `autopilot.DEFAULT_FOLLOW_DELAY` |
| `autopilot_paint_delay` | `5.0` | `AUTOPILOT_PAINT_DELAY` | `autopilot.DEFAULT_PAINT_DELAY` |
| `demo_fast_classify_time` | `5.0` | `DEMO_FAST_CLASSIFY_TIME` | `verification_engine.py` DEMO_FAST halved thresholds |
| `demo_fast_verify_time` | `8.0` | `DEMO_FAST_VERIFY_TIME` | `verification_engine.py` DEMO_FAST halved thresholds |
| `uav_speed_mps` | `60.0` | `UAV_SPEED_MPS` | `sim_engine.py` physics default |
| `detection_range_km` | `15.0` | `DETECTION_RANGE_KM` | sensor range default |
| `swarm_task_expiry_s` | `120.0` | `SWARM_TASK_EXPIRY_S` | `swarm_coordinator._TASK_EXPIRY_SECONDS` |
| `tick_rate_hz` | `10.0` | `TICK_RATE_HZ` | `simulation_loop.py` 10Hz tick |
| `max_turn_rate_dps` | `3.0` | `MAX_TURN_RATE_DPS` | `uav_physics.MAX_TURN_RATE` |
| `idle_count_threshold` | `3` | `IDLE_COUNT_THRESHOLD` | `sim_engine.MIN_IDLE_COUNT` |

### `src/python/tests/test_grid_sentinel_settings.py` (new)
26 tests covering:
- Default values for all 12 new fields
- Env-var override for all 12 fields
- Type assertions (float vs int)

## Test Results
- New tests: **26/26 passed**
- Full suite (excluding pre-existing broken `test_uav_kinematics.py`): **1746 passed**, 1 flaky pre-existing failure unrelated to this PR

## Notes
- No other files modified — future PRs will wire these settings into the consuming modules
- Physics constants (geometry orbit radii, confidence fade factors) remain as named constants in sim_engine.py per acceptance criteria
- `case_sensitive: False` in model_config means env vars are matched case-insensitively
