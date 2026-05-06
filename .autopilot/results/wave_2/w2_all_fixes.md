---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# Wave 2 Results — All 4 Tasks Complete

## W2-A: App.tsx Event Bridge (FIX-01 + FIX-02)
- **FIX-01**: Added `'spike'` to ALLOWED_ACTIONS set — spike events now reach backend
- **FIX-02**: Added `grid_sentinel:assignTarget` listener — selects drone + switches to ENEMIES tab
- **Files**: `src/frontend-react/src/App.tsx`
- **Status**: PASS

## W2-B: CesiumContextMenu (FIX-07 + FIX-08 + FIX-09 + FIX-10)
- **FIX-07**: Follow action changed from `scan_area` to `follow_target` with proper `drone_id`
- **FIX-08**: Paint action now includes `drone_id` from store
- **FIX-09**: Nominate changed to "Review Nomination" — navigates to MISSION tab instead of sending invalid WS message
- **FIX-10**: RTB now sends `move_drone` with theater base coordinates instead of invalid `rtb: true`
- **Files**: `src/frontend-react/src/cesium/CesiumContextMenu.tsx`
- **Status**: PASS

## W2-C: CommandPalette (FIX-04 + FIX-05 + FIX-06)
- **FIX-06**: Replaced `targets.filter(t => t.status === 'NOMINATED')` with `strikeBoard.filter(entry => entry.status === 'PENDING')`
- **FIX-05**: Changed `target_id: t.id` to `entry_id: entry.id` for approve_nomination
- **FIX-04**: Changed UAV command from `follow_target` (missing target_id) to `scan_area`
- **Files**: `src/frontend-react/src/overlays/CommandPalette.tsx`
- **Status**: PASS

## W2-D: DroneActionButtons (FIX-03 + FIX-15)
- **FIX-03**: Detail button now dispatches `grid_sentinel:openDetailMap` event with drone position
- **FIX-15**: Waypoint button now sets `trackedDrone(uav.id)` before toggling waypoint mode
- **Files**: `src/frontend-react/src/panels/assets/DroneActionButtons.tsx`
- **Status**: PASS

## Summary
- **Total fixes**: 11 (FIX-01 through FIX-10 + FIX-15)
- **Files modified**: 4
- **TypeScript**: Clean (pre-existing TS2352 in EngagementHistory.tsx only)
- **Backend tests**: 1811 passing (no regression)
