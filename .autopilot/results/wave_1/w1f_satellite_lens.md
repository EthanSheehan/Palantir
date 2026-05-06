---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# w1f — Satellite Lens

## Status: COMPLETE

## What Was Built

A satellite lens picture-in-picture inset Cesium viewer that syncs camera with the main globe view.

- `useSatelliteLens` hook manages lifecycle of a second Cesium.Viewer rendered into a small DOM container (300x200px, bottom-left of map canvas)
- Camera sync: `postRender` listener copies position/direction/up from main viewer to lens viewer each frame
- Toggle: S key or `grid_sentinel:toggleSatLens` custom DOM event
- Lens container styled with semi-transparent blue border, rounded corners, z-index 5, with a "SAT" text label overlay
- Cleanup on toggle-off and unmount destroys the lens viewer and removes its DOM container

## Files Created

- `src/frontend-react/src/cesium/useSatelliteLens.ts` — new hook

## Files Modified

- `src/frontend-react/src/cesium/CesiumContainer.tsx` — import + call `useSatelliteLens(viewerRef)`
- `src/frontend-react/src/overlays/MapModeBar.tsx` — added SAT toggle button and `satLensActive` state; S key also syncs button state

## Deviations from Plan

- Used `useState` in MapModeBar to sync button active state on both S-key and button click paths (plan only mentioned button click)
- The MapModeBar wrapper div got `display: flex; alignItems: center` to accommodate the SAT button sitting beside the ButtonGroup without wrapping
- No pre-existing `tsconfig` errors in our files — one pre-existing unrelated TS error in `EngagementHistory.tsx` was already present

## TypeScript

`npx tsc --noEmit` produces zero errors attributable to our files.
