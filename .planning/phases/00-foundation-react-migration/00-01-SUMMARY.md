---
phase: 00-foundation-react-migration
plan: "01"
subsystem: frontend-react
tags: [react, typescript, zustand, vite, blueprint, cesium]
dependency_graph:
  requires: []
  provides: [P0-BUILD, P0-STORE]
  affects: [all subsequent plans in phase 00]
tech_stack:
  added: [zustand@4.5.0, @blueprintjs/core@5.13.0, @blueprintjs/icons@5.14.0, vite-plugin-cesium@1.2.23]
  patterns: [Zustand flat store with action methods, Vite proxy for WS/API, Blueprint dark theme via body class]
key_files:
  created:
    - src/frontend-react/src/store/types.ts
    - src/frontend-react/src/store/SimulationStore.ts
    - src/frontend-react/src/shared/constants.ts
    - src/frontend-react/src/shared/geo.ts
    - src/frontend-react/src/vite-env.d.ts
    - src/frontend-react/src/App.tsx
    - src/frontend-react/src/main.tsx
    - src/frontend-react/index.html
    - src/frontend-react/package.json
    - src/frontend-react/tsconfig.json
  modified:
    - src/frontend-react/vite.config.ts
    - .gitignore
decisions:
  - "No StrictMode wrapper: Cesium Viewer double-mount breaks in StrictMode"
  - "Zustand v4 create() pattern (not v5 createStore): project locked to 4.5.0"
  - "setSimData handles sitrep_response + hitl_update inline to avoid extra re-renders"
  - "Added *.tsbuildinfo and package-lock.json to .gitignore (generated artifacts)"
metrics:
  duration: "1m 41s"
  completed_date: "2026-03-19"
  tasks_completed: 2
  tasks_total: 2
  files_created: 10
  files_modified: 2
---

# Phase 00 Plan 01: Foundation — Type Definitions, Zustand Store, and React Entry Point

One-liner: TypeScript interfaces, Zustand store with full sim + UI state, Blueprint dark-theme React entry, and Vite build all working cleanly.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix vite.config.ts + create type definitions + shared utilities | 11a1b92 | vite.config.ts, types.ts, constants.ts, geo.ts, vite-env.d.ts, .gitignore |
| 2 | Create Zustand store + main.tsx + App.tsx shell | 14680c1 | SimulationStore.ts, App.tsx, main.tsx, index.html, package.json, tsconfig.json |

## What Was Built

**Type system (`src/store/types.ts`):** 11 exported interfaces covering the full WebSocket payload — `UAV`, `Target`, `Zone`, `FlowLine`, `StrikeEntry`, `COA`, `TheaterBounds`, `TheaterInfo`, `AssistantMessage`, `HitlUpdate`, `SimStatePayload`. All fields derived from `api_main.py` broadcast format and vanilla JS modules.

**Shared constants (`src/shared/constants.ts`):** `MODE_STYLES`, `TARGET_MAP`, `STATE_COLORS`, `TARGET_STYLES`, `SEVERITY_STYLES` — exact color/label values from dronelist.js, targets.js, enemies.js. Plus `SENSOR_RANGE_KM`, `HFOV_DEG`, `EARTH_R`, `THREAT_RING_RADIUS`, `THREAT_RING_TYPES`, `MAX_ASSISTANT_MESSAGES`.

**Geo utilities (`src/shared/geo.ts`):** `haversineDist` (metres) and `bearing` (degrees 0-360) ported from dronecam.js.

**Zustand store (`src/store/SimulationStore.ts`):** Single `useSimStore` export. `setSimData` updates all sim arrays atomically and appends `sitrep_response`/`hitl_update` to `assistantMessages` (capped at 50). COAs cached per `entry_id`. UI state: `selectedDroneId`, `selectedTargetId`, `trackedDroneId`, `gridVisState` (0/1/2), `showAllWaypoints`, `droneCamVisible`, `isSettingWaypoint`.

**Entry point (`src/main.tsx`):** Blueprint CSS before icons CSS, `FocusStyleManager.onlyShowFocusOnTabs()`, no StrictMode.

**App shell (`src/App.tsx`):** Flex row layout — 300px dark sidebar + flex Cesium area. Placeholder for future components.

**Vite config:** `cesium()` before `react()` in plugins array. Dev server on :3000, proxies `/api` and `/ws` to localhost:8000.

## Verification Results

- `npx tsc --noEmit` — exits 0, no errors
- `npm run build` — exits 0, `built in 1.27s`
- `grep -c 'export' types.ts` — returns 11 (plan requires 10+)
- `grep 'cesium().*react()' vite.config.ts` — matches

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added *.tsbuildinfo and package-lock.json to .gitignore**
- Found during: Task 1 commit prep
- Issue: `tsconfig.tsbuildinfo` (TypeScript incremental build artifact) and `package-lock.json` were untracked and would clutter git history
- Fix: Added both patterns to the Node.js section of `.gitignore`
- Files modified: `.gitignore`
- Commit: 11a1b92

**2. [Rule 3 - Continuation] Task 1 files pre-existed in git from a prior session**
- The vite.config.ts fix and Task 1 files (types.ts, constants.ts, geo.ts, vite-env.d.ts) were already committed before this execution session (commit 3f4d7ad). They matched the plan spec exactly. No re-work was needed — Task 1 commit (11a1b92) captured only the .gitignore addition.

## Self-Check: PASSED

Files verified:
- FOUND: src/frontend-react/src/store/types.ts
- FOUND: src/frontend-react/src/store/SimulationStore.ts
- FOUND: src/frontend-react/src/shared/constants.ts
- FOUND: src/frontend-react/src/shared/geo.ts
- FOUND: src/frontend-react/src/vite-env.d.ts
- FOUND: src/frontend-react/src/App.tsx
- FOUND: src/frontend-react/src/main.tsx

Commits verified:
- FOUND: 11a1b92 (Task 1)
- FOUND: 14680c1 (Task 2)
