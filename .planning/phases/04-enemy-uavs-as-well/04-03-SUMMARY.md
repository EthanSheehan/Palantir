---
phase: 04-enemy-uavs-as-well
plan: 03
subsystem: sim_engine + api_main + theater_loader
tags: [enemy-uavs, evasion, intercept-kill, theater-config, demo-autopilot, websocket]
dependency_graph:
  requires: [04-01, 04-02]
  provides: [enemy-uav-full-lifecycle, intercept-kill-mechanic, theater-enemy-config, auto-intercept-demo]
  affects: [sim_engine, api_main, theater_loader, theaters/romania.yaml]
tech_stack:
  added: []
  patterns: [evasion-hysteresis, dwell-kill, theater-yaml-config, demo-autopilot-loop]
key_files:
  created: []
  modified:
    - src/python/sim_engine.py
    - src/python/api_main.py
    - src/python/theater_loader.py
    - theaters/romania.yaml
    - src/python/tests/test_enemy_uavs.py
decisions:
  - "Evasion triggers at fused_confidence > 0.5 with 15s cooldown — prevents mode thrashing under intermittent detection"
  - "_original_mode stored on EVADING entry so enemy returns to correct behavior after cooldown"
  - "Dwell kill: UAV holds position (vx=vy=0) in close range zone for 3s, then kills — avoids orbit drift causing premature exit"
  - "enemy_intercept_dispatched set in demo_autopilot prevents repeated dispatches per enemy UAV"
  - "JAMMING speed_kmh=0 means is_jamming=True but no speed override (JAMMING mode station-keeps anyway)"
metrics:
  duration: 298s
  completed_date: "2026-03-20"
  tasks_completed: 1
  files_modified: 5
---

# Phase 04 Plan 03: Enemy UAV Intercept Mechanics Summary

Evasion with hysteresis, intercept kill mechanic, theater YAML config, WS action, and demo autopilot auto-intercept — completes the enemy UAV full lifecycle.

## What Was Built

### Evasion Behavior with Hysteresis (`sim_engine.py`)

`EnemyUAV.update()` now:
- Triggers EVADING when `fused_confidence > 0.5` (and not already EVADING/DESTROYED)
- Stores `_original_mode` before entering EVADING
- Sets `evasion_cooldown = 15.0` seconds
- In EVADING: random heading changes at 1.5x speed, decrement cooldown
- Exits EVADING when `evasion_cooldown <= 0 AND fused_confidence < 0.3`

### Intercept Kill Mechanic (`sim_engine.py`)

- `command_intercept_enemy(uav_id, enemy_uav_id)`: sets UAV mode INTERCEPT, stores enemy id as `primary_target_id`
- `_update_enemy_intercept()`: approach at 1.5x speed, hold position in INTERCEPT_CLOSE_DEG zone, accumulate 3s dwell, then kill
- Kill: sets `enemy.mode = "DESTROYED"`, `enemy.vx = enemy.vy = 0`, UAV reverts to SEARCH
- `_update_tracking_modes()`: routes `primary_target_id >= 1000` to `_update_enemy_intercept()`

### Theater YAML Config (`theater_loader.py`, `theaters/romania.yaml`)

- `EnemyUAVUnitConfig` dataclass: behavior, count, speed_kmh (default 400.0)
- `EnemyUAVConfig` dataclass: tuple of units
- `TheaterConfig` gets optional `enemy_uavs: Optional[EnemyUAVConfig]` field
- `_parse_enemy_uavs()` parses the YAML list
- `_spawn_enemy_uavs()` reads theater config: spawns per behavior/count/speed, falls back to 3 RECON drones
- Romania theater: 2 RECON (400 km/h) + 1 JAMMING (0 km/h)

### WebSocket Action (`api_main.py`)

```python
elif action == "intercept_enemy":
    sim.command_intercept_enemy(payload["uav_id"], payload["enemy_uav_id"])
```

Schema: `{"uav_id": "int", "enemy_uav_id": "int"}`

### Demo Autopilot Auto-Intercept (`api_main.py`)

Checks enemy UAVs each loop iteration. When `fused_confidence > 0.7` and not already dispatched, finds nearest IDLE/SEARCH UAV and calls `command_intercept_enemy()`. Broadcasts `ASSISTANT_MESSAGE` to dashboard.

## Tests

10 new tests in 3 new classes:

- `TestEvasion` (4 tests): trigger, cooldown prevents thrash, returns to original mode, speed boost
- `TestInterceptKill` (4 tests): command sets INTERCEPT, kill at close range (31 ticks), UAV returns to SEARCH, DESTROYED no movement
- `TestTheaterConfig` (2 tests): enemy UAVs from YAML, count matches YAML (3 total)

All 387 tests green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Orbit drift caused dwell to stop accumulating**
- **Found during:** Task 1 GREEN phase debugging
- **Issue:** Tight orbit in dwell zone moved UAV tangentially, incrementally increasing dist > INTERCEPT_CLOSE_DEG, causing dwell to stall at ~0.7s
- **Fix:** Changed dwell logic to hold position (vx=vy=0) while within close range zone — avoids orbit drift
- **Files modified:** src/python/sim_engine.py (_update_enemy_intercept)
- **Commit:** f030530

## Self-Check: PASSED
