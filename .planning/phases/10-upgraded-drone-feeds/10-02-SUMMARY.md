---
phase: 10
plan: 02
subsystem: frontend-react/components
tags: [react, echarts, blueprint, hud, sigint, drone-feeds]
dependency_graph:
  requires: []
  provides: [SigintDisplay, SensorHUD, CamLayoutSelector]
  affects: [DroneCamPIP (Plan 03)]
tech_stack:
  added: []
  patterns: [ECharts heatmap ring buffer, Blueprint ButtonGroup layout toggle, DOM overlay HUD]
key_files:
  created:
    - src/frontend-react/src/components/SigintDisplay.tsx
    - src/frontend-react/src/components/SensorHUD.tsx
    - src/frontend-react/src/components/CamLayoutSelector.tsx
  modified:
    - src/frontend-react/src/store/types.ts
decisions:
  - Added fov_targets/sensor_quality to UAV interface (Plan 01 prereq) via Rule 3 auto-fix
  - ButtonGroup small prop absent in installed Blueprint version — omitted without visual loss
  - Compass tape uses 3x360=1080px inner div with translateX scroll — matches plan spec
  - Threat detection gates on drone.fov_targets inclusion before checking threat_range_km distance
metrics:
  duration: 142s
  completed: "2026-03-20"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 10 Plan 02: UI Components — SIGINT Display, Sensor HUD, Cam Layout Selector Summary

Three standalone React components ready for composition by Plan 03's DroneCamPIP rewrite: ECharts SIGINT waterfall heatmap with dark-blue-to-white color ramp, DOM overlay HUD with compass tape/fuel gauge/sensor status/threat warning, and Blueprint ButtonGroup layout toggle.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | SigintDisplay + CamLayoutSelector | bb0d99e | SigintDisplay.tsx, CamLayoutSelector.tsx, types.ts |
| 2 | SensorHUD DOM overlay | 31a195d | SensorHUD.tsx |

## Decisions Made

- **CamLayout/SensorMode types added inline** — Plan 01 prereq types were missing from types.ts; added as Rule 3 auto-fix (blocking issue) rather than halting execution.
- **ButtonGroup small prop** — Blueprint installed version lacks `small` prop on ButtonGroup; omitted without visual regression.
- **Ring buffer pattern** — `useRef<number[][]>` ring buffer + `useState` tick counter forces `useMemo` recalculation without re-creating the buffer on each render.
- **Threat gate** — `drone.fov_targets.includes(t.id)` pre-filters targets before haversine distance check, avoiding O(n) full target scans per render.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing CamLayout/SensorMode types from Plan 01**
- **Found during:** Task 1 (importing CamLayout in CamLayoutSelector)
- **Issue:** Plan 01 had not been executed; `CamLayout`, `SensorMode`, `fov_targets`, and `sensor_quality` were absent from types.ts
- **Fix:** Added all four missing type definitions to types.ts before building components
- **Files modified:** src/frontend-react/src/store/types.ts
- **Commit:** bb0d99e

**2. [Rule 1 - Bug] ButtonGroup `small` prop incompatibility**
- **Found during:** Task 1 TypeScript compilation
- **Issue:** `ButtonGroup` in installed Blueprint version does not accept `small` prop — TS2322 error
- **Fix:** Removed `small` prop from ButtonGroup; button sizing handled implicitly
- **Files modified:** src/frontend-react/src/components/CamLayoutSelector.tsx
- **Commit:** bb0d99e

## Self-Check: PASSED

- `src/frontend-react/src/components/SigintDisplay.tsx` — exists, exports SigintDisplay, contains `type.*heatmap`, `FREQ_BINS`, `TIME_SLOTS`, `animation: false`, `#000814`
- `src/frontend-react/src/components/CamLayoutSelector.tsx` — exists, exports CamLayoutSelector, contains `ButtonGroup`, SINGLE/PIP/SPLIT/QUAD
- `src/frontend-react/src/components/SensorHUD.tsx` — exists, exports SensorHUD, contains ProgressBar, heading_deg, THREAT, fuel_hours, pointerEvents none
- TypeScript: `npx tsc --noEmit` — no errors
- Commits bb0d99e and 31a195d — verified in git log
