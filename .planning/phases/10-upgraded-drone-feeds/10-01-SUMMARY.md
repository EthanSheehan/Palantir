---
phase: 10-upgraded-drone-feeds
plan: "01"
subsystem: drone-feeds
tags: [backend, frontend, sensor-rendering, canvas, zustand]
dependency_graph:
  requires: []
  provides: [fov_targets-serialization, sensor_quality-serialization, CamLayout-type, SensorMode-type, camLayout-store, useSensorCanvas-hook]
  affects: [sim_engine, SimulationStore, useDroneCam-replacement]
tech_stack:
  added: []
  patterns: [rAF-loop-with-getState, parameterized-canvas-hook, sensor-mode-dispatch]
key_files:
  created:
    - src/python/tests/test_drone_feed_fields.py
    - src/frontend-react/src/hooks/useSensorCanvas.ts
  modified:
    - src/python/sim_engine.py
    - src/frontend-react/src/store/types.ts
    - src/frontend-react/src/store/SimulationStore.ts
    - src/frontend-react/src/shared/constants.ts
key_decisions:
  - "_SENSOR_QUALITY_MAP is a class variable dict on SimulationModel — avoids per-call dict construction"
  - "_compute_fov_targets uses detection_range_km from target, falls back to 15.0 if None"
  - "lockPulsePhase is module-level in useSensorCanvas — persists across rAF frames without useRef"
  - "projectTarget() in useSensorCanvas takes width/height params instead of hardcoded WIDTH/HEIGHT"
  - "FUSION mode uses ctx.save()/clip()/translate()/restore() for isolated half-canvas rendering"
  - "primary_target_id drives reticle/lock-box; tracked_target_ids drives dashed bounding boxes"
metrics:
  duration: "275s"
  completed_date: "2026-03-20"
  tasks_completed: 2
  files_modified: 6
---

# Phase 10 Plan 01: Drone Feed Foundation Summary

Backend serializes fov_targets (detected target IDs in FOV) and sensor_quality (float 0-1 by mode) per UAV; frontend gains CamLayout/SensorMode types, camLayout Zustand state, and the parameterized useSensorCanvas hook with EO/IR, SAR, FUSION, and SIGINT render modes.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Backend fov_targets + sensor_quality fields and tests | d5bdf94 |
| 2 | Frontend types, Zustand store, and useSensorCanvas hook | efb1e72 |

## What Was Built

### Task 1 — Backend (sim_engine.py)

- `_compute_fov_targets(uav)` helper: iterates `self.targets`, skips UNDETECTED, distance-checks with `math.hypot / DEG_PER_KM` against `detection_range_km` (default 15 km).
- `_SENSOR_QUALITY_MAP` class variable: PAINT=1.0, VERIFY=0.9, FOLLOW/INTERCEPT=0.8, SUPPORT=0.7, SEARCH/other=0.6, OVERWATCH=0.5.
- `get_state()` UAV dict now includes `fov_targets` (list[int]) and `sensor_quality` (float).
- 5 TDD tests in `test_drone_feed_fields.py` — all pass.

### Task 2 — Frontend

- `CamLayout = 'SINGLE' | 'PIP' | 'SPLIT' | 'QUAD'` and `SensorMode = 'EO_IR' | 'SAR' | 'SIGINT' | 'FUSION'` in types.ts.
- `fov_targets: number[]` and `sensor_quality: number` added to UAV interface.
- `SENSOR_COLORS` record added to constants.ts.
- `SimulationStore` gains `camLayout: CamLayout` state and `setCamLayout` action.
- `useSensorCanvas(droneId, sensorMode, canvasRef)` hook:
  - EO/IR: dark green `#0a1a0a` bg, grid, radial thermal glow on targets, terrain noise, green crosshair/reticle/lock-box, HUD.
  - SAR: dark `#0d0800` bg, moving amber scan-line, target velocity vectors, amber echo rings, noise dots.
  - FUSION: split-screen via `ctx.save()/clip()` — EO/IR left half, SAR right half, center divider `#334155`.
  - SIGINT: dark blue placeholder awaiting SigintDisplay component (Plan 02).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `src/python/sim_engine.py` contains `def _compute_fov_targets`
- [x] `src/python/sim_engine.py` contains `"fov_targets"` in get_state() UAV dict
- [x] `src/python/sim_engine.py` contains `"sensor_quality"` in get_state() UAV dict
- [x] `src/python/tests/test_drone_feed_fields.py` contains `def test_fov_targets_and_sensor_quality`
- [x] `src/frontend-react/src/store/types.ts` contains `fov_targets: number[]`
- [x] `src/frontend-react/src/store/types.ts` contains `sensor_quality: number`
- [x] `src/frontend-react/src/store/types.ts` contains `export type CamLayout`
- [x] `src/frontend-react/src/store/types.ts` contains `export type SensorMode`
- [x] `src/frontend-react/src/store/SimulationStore.ts` contains `camLayout`
- [x] `src/frontend-react/src/store/SimulationStore.ts` contains `setCamLayout`
- [x] `src/frontend-react/src/hooks/useSensorCanvas.ts` contains `export function useSensorCanvas`
- [x] `src/frontend-react/src/hooks/useSensorCanvas.ts` contains `drawEoIrFrame`
- [x] `src/frontend-react/src/hooks/useSensorCanvas.ts` contains `drawSarFrame`
- [x] `src/frontend-react/src/hooks/useSensorCanvas.ts` contains `drawFusionFrame`
- [x] `src/frontend-react/src/hooks/useSensorCanvas.ts` contains `primary_target_id`
- [x] `src/frontend-react/src/shared/constants.ts` contains `SENSOR_COLORS`
- [x] Python tests pass (5/5)
- [x] TypeScript compiles with no errors

## Self-Check: PASSED
