---
phase: 01
plan: 03
subsystem: frontend-react
tags: [sensor-fusion, react, cesium, typescript, echarts, ui-components]
dependency_graph:
  requires: [01-02]
  provides: [P1-TS-TYPES, P1-FUSIONBAR, P1-BADGE, P1-ENEMYCARD, P1-DRONECARD, P1-CESIUM-RING]
  affects: [src/frontend-react/src/panels/enemies, src/frontend-react/src/panels/assets, src/frontend-react/src/cesium]
tech_stack:
  added: []
  patterns: [stacked-echarts-bar, blueprint-intent-badge, cesium-ellipse-overlay]
key_files:
  created:
    - src/frontend-react/src/panels/enemies/FusionBar.tsx
    - src/frontend-react/src/panels/enemies/SensorBadge.tsx
  modified:
    - src/frontend-react/src/store/types.ts
    - src/frontend-react/src/panels/enemies/EnemyCard.tsx
    - src/frontend-react/src/panels/assets/DroneCard.tsx
    - src/frontend-react/src/cesium/useCesiumTargets.ts
    - src/python/sim_engine.py
    - src/python/tests/test_sim_integration.py
decisions:
  - FusionBar uses useMemo with per-sensor color mapping (EO_IR=blue, SAR=green, SIGINT=amber)
  - Fusion ring uses direct update pattern (not CallbackProperty) matching existing threat ring
  - fusionRingRef cleanup added to both entity removal and targets.forEach tail
  - fused_confidence only written when contributions present (not zeroed on empty tick)
metrics:
  duration: ~12min
  completed_date: "2026-03-19"
  tasks_completed: 3
  files_modified: 8
---

# Phase 1 Plan 03: Sensor Fusion UI Components Summary

FusionBar (ECharts stacked bar) and SensorBadge (Blueprint Tag) integrated into EnemyCard and DroneCard; Cesium cyan fusion ring added around targets scaling with sensor_count.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Extend TypeScript types, create FusionBar and SensorBadge | 6a7db18 (prior plan) |
| 2 | Integrate into EnemyCard, DroneCard, and Cesium fusion ring | 3ee848c |

## What Was Built

**Task 1 (pre-existing from prior plan execution):**
- `types.ts` already extended with `SensorContributionPayload`, UAV `tracked_target_ids`/`primary_target_id`, and all Target Phase 1 fields
- `FusionBar.tsx` — stacked ECharts bar chart with `stack: 'fusion'`, EO_IR=#4A90E2, SAR=#7ED321, SIGINT=#F5A623
- `SensorBadge.tsx` — Blueprint Tag with Intent.SUCCESS (3+), Intent.WARNING (2), Intent.NONE (1)

**Task 2:**
- `EnemyCard.tsx` — added `<SensorBadge>` in header row, `<FusionBar>` with contributing UAV list (per-sensor color coded)
- `DroneCard.tsx` — added TRACKING row showing `tracked_target_ids`, primary target highlighted in gold (#facc15) with PRIMARY badge
- `useCesiumTargets.ts` — added `fusionRingRef`, cyan ellipse per target when `sensor_count > 0`, radius = 1000 + sensor_count*500m, alpha = min(0.6, 0.2*sensor_count)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed fused_confidence zeroing for tracked detected targets**
- **Found during:** Task 3 (checkpoint verification — Python tests)
- **Issue:** `sim_engine.py` unconditionally called `fuse_detections(contributions)` and wrote its result to `t.fused_confidence`, even when `contributions` was empty (returns 0.0). A target in DETECTED state with `tracked_by_uav_ids` set would have its `fused_confidence` zeroed every tick when no UAV happened to be in detection range that tick, while keeping `state=DETECTED`.
- **Fix:** Moved all confidence/contribution writes inside the `if contributions:` branch. The else branch (fade logic) now handles the empty case, which correctly preserves or fades confidence.
- **Files modified:** `src/python/sim_engine.py`, `src/python/tests/test_sim_integration.py`
- **Commit:** ce9a80b

**2. [Rule 1 - Bug] Fixed test assertion excluding engagement states**
- **Found during:** same investigation
- **Issue:** `test_detected_targets_have_fused_confidence` tested all `state != "UNDETECTED"` targets including ENGAGED/DESTROYED/NEUTRALIZED, which skip the detection loop by design and can legitimately have `fused_confidence=0`.
- **Fix:** Added `skip_states` set excluding ENGAGED, DESTROYED, NEUTRALIZED from the assertion.
- **Commit:** ce9a80b

## Task 3: Visual Verification (Human Checkpoint)

User verified the app running in demo mode. Two issues found and fixed:

**Fix 1: ENEMIES tab bouncing too fast** — EnemyCard and FusionBar re-rendered every 10Hz tick.
- Wrapped EnemyCard in `React.memo` with custom comparator (rounds lat/lon to 3 decimals, confidence to whole %)
- Wrapped FusionBar in `React.memo` with stable contribution key, disabled ECharts animation
- Commit: b725df1

**Fix 2: Inconsistent target naming** — Some cards/labels showed type names (SAM, TEL) instead of uniform TARGET-N.
- Changed EnemyCard badge to always show "TGT"
- Changed Cesium label to `TARGET-{id}` and SVG icon text to "TGT"
- Commits: 78cd6d1, 80665c5

## Self-Check: PASSED

All files present. All commits confirmed in git log. 258/258 Python tests pass. TypeScript noEmit and npm run build exit 0. User visually approved.
