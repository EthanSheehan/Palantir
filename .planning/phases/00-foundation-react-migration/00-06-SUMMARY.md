---
phase: "00"
plan: "06"
subsystem: frontend-react/cesium
tags: [cesium, hooks, overlays, compass, drone-cam, click-handlers, range-rings, waypoints]
dependency_graph:
  requires: ["00-03", "00-05"]
  provides: [useCesiumCompass, useCesiumMacroTrack, useCesiumClickHandlers, useCesiumRangeRings, useCesiumWaypoints, useCesiumLockIndicators, CameraControls, DroneCamPIP, DemoBanner, DetailMapDialog]
  affects: [CesiumContainer, App]
tech_stack:
  added: []
  patterns: [CallbackProperty, preUpdate-listener, requestAnimationFrame-canvas, custom-window-events, conditional-second-cesium-viewer]
key_files:
  created:
    - src/frontend-react/src/cesium/useCesiumCompass.ts
    - src/frontend-react/src/cesium/useCesiumMacroTrack.ts
    - src/frontend-react/src/cesium/useCesiumClickHandlers.ts
    - src/frontend-react/src/cesium/useCesiumRangeRings.ts
    - src/frontend-react/src/cesium/useCesiumWaypoints.ts
    - src/frontend-react/src/cesium/useCesiumLockIndicators.ts
    - src/frontend-react/src/cesium/CameraControls.tsx
    - src/frontend-react/src/cesium/DetailMapDialog.tsx
    - src/frontend-react/src/hooks/useDroneCam.ts
    - src/frontend-react/src/overlays/DroneCamPIP.tsx
    - src/frontend-react/src/overlays/DemoBanner.tsx
  modified:
    - src/frontend-react/src/cesium/CesiumContainer.tsx
    - src/frontend-react/src/App.tsx
decisions:
  - "Window custom events bridge Cesium hooks to WebSocket: grid_sentinel:send, grid_sentinel:placeWaypoint, grid_sentinel:openDetailMap — avoids threading the sendMessage prop through Cesium imperative code"
  - "useCesiumMacroTrack defers first position recording by one frame to avoid camera jump on flyTo completion"
  - "ctx non-null assertion via reassignment (const ctx: CanvasRenderingContext2D = ctxRaw) bypasses TypeScript flow narrowing limits in nested functions"
  - "DetailMapDialog defers viewer init to rAF after open state change to ensure container is in DOM"
metrics:
  duration: ~10min
  completed: "2026-03-19"
  tasks: 2
  files: 13
---

# Phase 0 Plan 06: Cesium Interaction + Overlay System Summary

Compass, drone click-selection, range rings, waypoints, lock indicators, drone cam PIP, camera controls, demo banner, and detail map dialog — completing the interactive Cesium experience with full overlay system.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | 6 remaining Cesium hooks: compass, macro track, click handlers, range rings, waypoints, lock indicators | b8a85b4 |
| 2 | CameraControls, DroneCamPIP, DemoBanner, DetailMapDialog + wire CesiumContainer + App | c0e2560 |

## What Was Built

**Task 1 — Cesium Interaction Hooks**

- `useCesiumCompass`: Compass needle (2000m forward vector) and ring (1500m radius, 64 segments) using `CallbackProperty`. Follows tracked drone `_lastHeading` or mouse position when no drone tracked. Yellow (#facc15) polylines clamped to ground.

- `useCesiumMacroTrack`: `preUpdate` event listener that applies camera position delta to follow the tracked drone without locking `trackedEntity`. First frame skips delta to avoid camera jump after flyTo.

- `useCesiumClickHandlers`: Single-click for drone macro selection (250ms debounce) or target selection, double-click for third-person tracking or spike action. Waypoint-setting mode intercepts clicks to send `move_drone` via `grid_sentinel:send` window event.

- `useCesiumRangeRings`: 10 concentric rings (1m–50km radius, 2000m–0m altitude) using `CallbackProperty` centered on waypoint or drone entity. `toggleRangeRings(droneId)` exposes toggle.

- `useCesiumWaypoints`: Green cylinder (2000m tall) + dashed polyline trajectory per drone. Listens for `grid_sentinel:placeWaypoint` window events. Visibility controlled by `showAllWaypoints` store flag and tracked drone ID. Removes waypoints when drone exits REPOSITIONING mode.

- `useCesiumLockIndicators`: Subscribes to store `uavs`. Adds red ellipse (500m radius, 0.8 alpha outline) on target when UAV in PAINT mode, removes when mode changes.

**Task 2 — Overlays and Assembly**

- `CameraControls`: Globe return + X decouple buttons, absolute top-left of viewer. Only renders when `trackedDroneId !== null`. Globe button flies to theater center then decouples.

- `useDroneCam`: Full `requestAnimationFrame` render loop with #141a14 background, grid, target shapes (diamond/triangle/rect/square/circle/hexagon), bounding box corners, reticle, pulsing lock box, target info box, HUD (telemetry, position, mode, tracking), crosshair, corner brackets. Cleanup cancels RAF on unmount.

- `DroneCamPIP`: 400x300 canvas overlay at bottom-right. Shows when `selectedDroneId !== null && droneCamVisible`. Header with DRONE CAM label and close button.

- `DemoBanner`: 40px full-width red banner (rgba 15% background, 1px border) when `demoMode === true`. Monospace, uppercase, centered.

- `DetailMapDialog`: Blueprint-free dialog containing a second Cesium Viewer with locked camera, 150km range constraint circle (red). Click inside constraint sends `move_drone` + places waypoint. Click outside flashes amber. Deferred viewer init ensures container is in DOM before Cesium initializes.

- `CesiumContainer` updated: wires all 6 new hooks, adds `CameraControls` and `DroneCamPIP` as sibling overlays.

- `App` updated: flex column wrapping `DemoBanner` + content row. `DetailMapDialog` rendered at app root. `grid_sentinel:send` window events bridged to `sendMessage` WebSocket function.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Window event bridge for WebSocket communication**
- **Found during:** Task 1 (useCesiumClickHandlers)
- **Issue:** Cesium hooks live outside React component tree — no clean way to access `sendMessage` from WebSocketContext without prop drilling through CesiumContainer
- **Fix:** Added `grid_sentinel:send` and `grid_sentinel:placeWaypoint` window events dispatched from Cesium hooks; App.tsx bridge listens and calls `sendMessage`
- **Files modified:** App.tsx, useCesiumClickHandlers.ts, useCesiumWaypoints.ts, DetailMapDialog.tsx

**2. [Rule 1 - Bug] TypeScript ctx null narrowing in nested functions**
- **Found during:** Task 2 verification (tsc --noEmit)
- **Issue:** TypeScript can't narrow `ctx` variable through nested function closures even after null check
- **Fix:** Reassigned `const ctx: CanvasRenderingContext2D = ctxRaw` after null guard to produce non-null typed variable
- **Files modified:** useDroneCam.ts

**3. [Rule 1 - Bug] skyAtmosphere possibly undefined in DetailMapDialog**
- **Found during:** Task 2 verification (tsc --noEmit)
- **Issue:** `viewer.scene.skyAtmosphere` typed as possibly undefined in some Cesium versions
- **Fix:** Added existence check before property access
- **Files modified:** DetailMapDialog.tsx

## Self-Check: PASSED

Files verified present:
- src/frontend-react/src/cesium/useCesiumCompass.ts
- src/frontend-react/src/cesium/useCesiumMacroTrack.ts
- src/frontend-react/src/cesium/useCesiumClickHandlers.ts
- src/frontend-react/src/cesium/useCesiumRangeRings.ts
- src/frontend-react/src/cesium/useCesiumWaypoints.ts
- src/frontend-react/src/cesium/useCesiumLockIndicators.ts
- src/frontend-react/src/cesium/CameraControls.tsx
- src/frontend-react/src/cesium/DetailMapDialog.tsx
- src/frontend-react/src/hooks/useDroneCam.ts
- src/frontend-react/src/overlays/DroneCamPIP.tsx
- src/frontend-react/src/overlays/DemoBanner.tsx

Commits: b8a85b4, c0e2560

Build: passed (npm run build, ✓ built in 6.24s)
