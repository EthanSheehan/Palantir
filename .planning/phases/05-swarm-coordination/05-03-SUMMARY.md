---
phase: 05-swarm-coordination
plan: 03
subsystem: frontend-react
tags: [swarm, cesium, zustand, typescript, react]
dependency_graph:
  requires: [05-01]
  provides: [swarm-frontend-ui, swarm-cesium-lines]
  affects: [EnemiesTab, CesiumContainer]
tech_stack:
  added: []
  patterns: [React.memo custom comparator, Cesium PolylineDashMaterialProperty, Zustand store subscription]
key_files:
  created:
    - src/frontend-react/src/panels/enemies/SwarmPanel.tsx
    - src/frontend-react/src/cesium/useCesiumSwarmLines.ts
  modified:
    - src/frontend-react/src/store/types.ts
    - src/frontend-react/src/store/SimulationStore.ts
    - src/frontend-react/src/panels/enemies/EnemiesTab.tsx
    - src/frontend-react/src/cesium/CesiumContainer.tsx
decisions:
  - SwarmPanel uses React.memo with custom comparator checking sensor coverage set and assigned_uav_ids length only — avoids re-rendering on every tick
  - 'SUPPORT' UAV mode was already present in types.ts from Phase 05 Plan 01 — no duplicate addition needed
  - PolylineDashMaterialProperty chosen over PolylineGlowMaterialProperty for semantic distinction between flow lines (glow) and swarm lines (dash)
  - UAV altitude 2000m, target altitude 500m for swarm lines — provides visual depth separation on globe
metrics:
  duration: 150s
  completed: "2026-03-20"
  tasks: 2/2
  files: 6
---

# Phase 05 Plan 03: React Swarm Frontend Summary

React frontend for swarm coordination — SwarmTask TypeScript types, Zustand store wiring, SwarmPanel sensor coverage indicator with request/release controls, and dashed cyan Cesium polylines connecting SUPPORT UAVs to their targets.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | SwarmTask types, store wiring, SwarmPanel, EnemiesTab | 930872e | types.ts, SimulationStore.ts, SwarmPanel.tsx, EnemiesTab.tsx |
| 2 | Cesium swarm lines hook + CesiumContainer composition | 0fdf17e | useCesiumSwarmLines.ts, CesiumContainer.tsx |

## What Was Built

### Task 1: Types, Store, SwarmPanel, EnemiesTab

- Added `SwarmTask` interface to `types.ts` with `target_id`, `assigned_uav_ids`, `sensor_coverage`, `formation_type`
- Added `swarm_tasks?: SwarmTask[]` to `SimStatePayload` (optional for backward compat)
- Added `swarmTasks: SwarmTask[]` to `SimState` interface and Zustand store initial state
- Updated `setSimData` to map `data.swarm_tasks || []` into `swarmTasks`
- Created `SwarmPanel.tsx` — renders 3 sensor coverage indicators (EO/IR, SAR, SIGINT) with filled dot (covered) or hollow dot (gap) per sensor type
- REQUEST button dispatches `palantir:send` with `action: 'request_swarm'`; shown when no swarm assigned
- RELEASE button dispatches `palantir:send` with `action: 'release_swarm'`; shown when swarm active
- `SwarmPanel` wrapped in `React.memo` with custom comparator — only re-renders on sensor coverage set change or assigned UAV count change
- `EnemiesTab.tsx` builds `swarmByTarget` lookup map and renders `<SwarmPanel>` beneath each `<EnemyCard>`

### Task 2: Cesium Swarm Lines

- Created `useCesiumSwarmLines.ts` following exact pattern of `useCesiumFlowLines.ts`
- Subscribes to `useSimStore`, reads `swarmTasks`, `uavs`, `targets`
- For each swarm task, iterates `assigned_uav_ids` and draws a dashed cyan polyline from UAV position (2000m) to target position (500m)
- Uses `PolylineDashMaterialProperty` with `Cesium.Color.CYAN.withAlpha(0.7)`, `dashLength: 16`, `dashPattern: 255`
- Full teardown: entities removed on unsubscribe and component unmount
- `CesiumContainer.tsx` imports and calls `useCesiumSwarmLines(viewerRef)` after `useCesiumFlowLines`

## Deviations from Plan

None — plan executed exactly as written.

Note: `'SUPPORT'` was already present in the UAV mode union type in `types.ts` from Phase 05 Plan 01. The plan instruction to add it was a no-op (correct outcome, no duplicate).

## Self-Check: PASSED

Files exist:
- FOUND: src/frontend-react/src/panels/enemies/SwarmPanel.tsx
- FOUND: src/frontend-react/src/cesium/useCesiumSwarmLines.ts

Commits exist:
- FOUND: 930872e feat(05-03): add SwarmTask types, store wiring, SwarmPanel, EnemiesTab integration
- FOUND: 0fdf17e feat(05-03): add useCesiumSwarmLines hook and compose into CesiumContainer

TypeScript: compiles without errors (npx tsc --noEmit exit 0)
