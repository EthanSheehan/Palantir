# W2-001: Split sim_engine.py God Module

## Status: COMPLETE

## Changes Made

### New Files Created
- `src/python/target_behavior.py` (205 lines) — Target class, ground unit behaviors (stationary, shoot-and-scoot, patrol, ambush), target state constants, emitting/concealment logic
- `src/python/uav_physics.py` (199 lines) — UAV class, fixed-wing flight model (_turn_toward, loiter, RTB, repositioning), sensor distribution, fuel management
- `src/python/enemy_uav_engine.py` (129 lines) — EnemyUAV class, adversary behaviors (RECON loiter, ATTACK approach, JAMMING station-keep, EVADING maneuvers with cooldown)

### Modified Files
- `src/python/sim_engine.py` (1598 -> 1090 lines) — Now a thin SimulationModel orchestrator that imports entity classes from sub-modules. All existing public names re-exported for backward compatibility.
- `src/python/sensor_model.py` — Added `altitude_m` parameter to `compute_pd()` and `evaluate_detection()`. Altitude penalty formula: `max(0, (altitude_m - 1000) / 10000)`. At default 3000m, penalty = 0.2 (small degradation).

### Removed
- Stale "VIEWING" mode comment from UAV.update() (replaced with accurate reference to SimulationModel._update_tracking_modes())

## Acceptance Criteria

| Criteria | Status |
|----------|--------|
| Each engine in its own file | DONE — target_behavior.py, uav_physics.py, enemy_uav_engine.py |
| SimulationOrchestrator in sim_engine.py owns only tick() loop and coordination | DONE — sim_engine.py contains only SimulationModel with tick(), commands, and get_state() |
| altitude_penalty in sensor_model.py applied | DONE — new altitude_m param with formula max(0, (alt-1000)/10000) |
| Stale VIEWING mode comment removed | DONE |
| ALL existing tests pass after the split | DONE — 545 passed (excluding untracked files from other parallel work) |

## Test Results
```
545 passed, 68 warnings in 31.07s
```
All 168 sim_engine-dependent tests pass individually (test_enemy_uavs, test_drone_modes, test_sim_integration, test_rtb_navigation, test_sensor_spawn, test_drone_feed_fields, test_feeds).

## Architecture After Split
```
sim_engine.py (1090 lines) — SimulationModel orchestrator
  imports from:
    ├── target_behavior.py (205 lines) — Target class + constants
    ├── uav_physics.py (199 lines) — UAV class + flight physics
    ├── enemy_uav_engine.py (129 lines) — EnemyUAV class + behaviors
    ├── sensor_model.py — probabilistic detection (now with altitude_penalty)
    ├── sensor_fusion.py — multi-sensor fusion
    ├── verification_engine.py — state machine
    └── swarm_coordinator.py — task assignment
```

All existing imports from sim_engine continue to work — backward compatibility preserved via re-exports.
