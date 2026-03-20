---
phase: 04-enemy-uavs-as-well
plan: 01
subsystem: sim-engine
tags: [enemy-uav, sensor-detection, simulation, tdd, python]
dependency_graph:
  requires: []
  provides: [EnemyUAV class, enemy UAV detection loop, enemy_uavs state broadcast]
  affects: [sim_engine.py, sensor_model.py, SimulationModel.tick, SimulationModel.get_state]
tech_stack:
  added: []
  patterns: [fixed-wing physics reuse, sensor fusion pipeline for new entity type]
key_files:
  created:
    - src/python/tests/test_enemy_uavs.py
  modified:
    - src/python/sim_engine.py
    - src/python/sensor_model.py
decisions:
  - EnemyUAV IDs start at 1000 to avoid collision with target IDs (0-30) and UAV IDs (0-19)
  - EnemyUAV._turn_toward uses MAX_TURN_RATE without 3x multiplier (no repositioning urgency)
  - JAMMING mode sets is_jamming=True enabling SIGINT detection via emitting gate
  - EVADING mode stubbed as RECON loiter (Plan 03 will implement actual evasion)
  - Confidence fade: fused_confidence * 0.95 per tick when no sensor contact, detected clears at < 0.1
  - _spawn_enemy_uavs spawns 3 enemies (IDs 1000-1002) at random positions within theater bounds
metrics:
  duration: 318s
  completed: "2026-03-20"
  tasks: 2
  files_changed: 3
---

# Phase 04 Plan 01: EnemyUAV Class + Detection Loop Summary

EnemyUAV entity with RECON/ATTACK/JAMMING behaviors, fixed-wing physics, sensor detection via evaluate_detection() pipeline, and get_state() broadcast under "enemy_uavs" key.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TDD EnemyUAV class + behaviors + RCS entry | 69598ea | sim_engine.py, sensor_model.py, test_enemy_uavs.py |
| 2 | TDD enemy UAV detection loop in SimulationModel.tick() | 1e06966 | sim_engine.py, test_enemy_uavs.py |

## What Was Built

### EnemyUAV class (sim_engine.py)

New entity class after the UAV class (~line 389). Fields: id, x, y, vx, vy, heading_deg, mode, behavior, detected, fused_confidence, sensor_count, sensor_contributions, is_jamming, speed, evasion_cooldown, attack_waypoint.

Three active behaviors:
- RECON: circular loiter using `heading_rad += MAX_TURN_RATE * dt_sec` (same as UAV SEARCH mode)
- ATTACK: direct approach to `attack_waypoint` using `_turn_toward()`, full ENEMY_SPEED
- JAMMING: vx=0, vy=0, is_jamming=True (station-keeping, SIGINT-visible)
- EVADING: stub, loiters like RECON (Plan 03)
- DESTROYED: no movement

`_turn_toward()` mirrors UAV's method but without the 3x multiplier (no urgency).

### sensor_model.py change

Added `"ENEMY_UAV": 0.1` to `RCS_TABLE` — small drone RCS (low observable).

### SimulationModel changes

- `self.enemy_uavs: List[EnemyUAV] = []` in `__init__`
- `_spawn_enemy_uavs()` — spawns 3 RECON enemies at IDs 1000-1002 at random positions within theater bounds, called from `initialize()`
- `_find_enemy_uav(enemy_uav_id)` — O(n) lookup in enemy_uavs list
- `get_state()` — new "enemy_uavs" key with payload: {id, lon, lat, mode, behavior, heading_deg, detected, fused_confidence, sensor_count, is_jamming}

### tick() detection loop (Task 2)

Two new sections after the ground target detection + verification steps:

**Section 9b** — enemy UAV movement update:
```python
for e in self.enemy_uavs:
    if e.mode != "DESTROYED":
        e.update(dt_sec, self.bounds)
```

**Section 10** — Enemy UAV Detection:
Mirrors the ground target detection loop. For each non-DESTROYED enemy UAV:
- Iterates all non-RTB/REPOSITIONING friendly UAVs
- Computes aspect angle for each UAV-enemy pair
- Calls `evaluate_detection(..., target_type="ENEMY_UAV", emitting=e.is_jamming)`
- Accumulates SensorContributions and calls `fuse_detections(contributions)`
- Updates e.fused_confidence, e.sensor_count, e.sensor_contributions, e.detected
- When no contributions: fused_confidence *= 0.95, detected clears at < 0.1

The `emitting=e.is_jamming` parameter is the key mechanic that makes JAMMING enemies detectable by SIGINT (requires_emitter=True gate). Non-jamming enemies are invisible to SIGINT-only UAVs.

## Test Results

21 tests in test_enemy_uavs.py, all pass:
- TestEnemyUAVSpawn (4 tests): creation, ID range, mode validation, spawn count
- TestEnemyUAVMovement (4 tests): RECON loiter, ATTACK approach, JAMMING station-keeping, turn rate bound
- TestSeparation (3 tests): not in targets, _find_enemy_uav works, list exists
- TestGetState (2 tests): key exists, payload shape
- TestEnemyUAVDetection (5 tests): nearby detection, distant non-detection, confidence positive, sensor count, fade
- TestJammingDetection (2 tests): SIGINT detects jamming, SIGINT cannot detect non-jamming
- TestPerformance (1 test): 100 ticks with 8 enemies in < 10 seconds

Full regression suite: 377/377 pass.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED
