---
phase: 03-drone-modes-autonomy
plan: 03
subsystem: frontend-react
tags: [autonomy-ui, react, typescript, blueprint, zustand, websocket]
dependency_graph:
  requires: [03-02]
  provides: [autonomy-toggle-ui, transition-toast-ui, drone-mode-source-ui]
  affects: [frontend-react]
tech_stack:
  added: []
  patterns: [Blueprint SegmentedControl, inline countdown with setInterval, Zustand selector pattern]
key_files:
  created:
    - src/frontend-react/src/panels/mission/AutonomyToggle.tsx
    - src/frontend-react/src/panels/assets/TransitionToast.tsx
  modified:
    - src/frontend-react/src/store/types.ts
    - src/frontend-react/src/store/SimulationStore.ts
    - src/frontend-react/src/shared/constants.ts
    - src/frontend-react/src/panels/assets/DroneModeButtons.tsx
    - src/frontend-react/src/panels/assets/DroneCard.tsx
    - src/frontend-react/src/panels/mission/MissionTab.tsx
decisions:
  - "Blueprint SegmentedControl `options` prop requires mutable array — `as const` not compatible"
  - "Blueprint5 ButtonGroup lacks `small` prop — removed; use Button `small` prop directly instead"
  - "useCesiumDrones already uses MODE_STYLES lookup with IDLE fallback — no change needed for new mode colors"
  - "TransitionToast renders inline (not OverlayToaster) per plan research — simpler, no async complexity"
metrics:
  duration: 246s
  completed: "2026-03-20"
  tasks_completed: 2
  files_changed: 8
---

# Phase 03 Plan 03: Autonomy UI Components Summary

React frontend components for the 3-tier autonomy system: AutonomyToggle control, TransitionToast for supervised-mode HITL decisions, updated DroneCard with mode source indicator, new SUPPORT/VERIFY mode buttons.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Update types, store, and constants for autonomy system | 62063d3 |
| 2 | Create AutonomyToggle, TransitionToast, update DroneCard/ModeButtons/MissionTab | bb54e25 |

## What Was Built

**AutonomyToggle** (`panels/mission/AutonomyToggle.tsx`): Blueprint SegmentedControl with MANUAL / SUPERVISED / AUTONOMOUS options. Sends `set_autonomy_level` WS action and updates Zustand store on value change. Mounted above TheaterSelector in MissionTab.

**TransitionToast** (`panels/assets/TransitionToast.tsx`): Inline card rendered inside DroneCard when a UAV has a pending autonomous mode transition. Shows UAV ID, target mode, reason, countdown progress bar (setInterval, 1s), and Approve/Reject buttons that send `approve_transition` / `reject_transition` WS actions. Displays "Auto-approved" text when countdown reaches zero.

**DroneCard updates**: Reads `pendingTransitions` from Zustand store. Renders `AUTO` tag badge next to mode label when `uav.mode_source === 'AUTO'`. Renders TransitionToast component when a pending transition exists.

**DroneModeButtons updates**: Added SUPPORT (teal, `#00b3a4`) and VERIFY (amber, `#d97008`) buttons, both requiring a selected target. Uses MODE_STYLES for colors. ACTION_FOR_MODE mapping extended for both.

**Types/Store/Constants**:
- UAV mode union extended: `SUPPORT | VERIFY | OVERWATCH | BDA`
- UAV interface: added `autonomy_override`, `mode_source`, `pending_transition`
- SimStatePayload: added `autonomy_level`
- Zustand store: added `autonomyLevel`, `pendingTransitions`, `setAutonomyLevel`
- `setSimData`: extracts `autonomy_level` and `pending_transition` per UAV each tick
- MODE_STYLES: 4 new entries (SUPPORT/#00b3a4, VERIFY/#d97008, OVERWATCH/#5c5fd6, BDA/#7f8fa4)

**Cesium**: No changes needed — `useCesiumDrones` already uses `MODE_STYLES[uav.mode] || MODE_STYLES.IDLE` fallback, so new modes render with correct colors automatically.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Blueprint SegmentedControl readonly array incompatibility**
- **Found during:** Task 2 TypeScript check
- **Issue:** `as const` makes the OPTIONS array `readonly`, which Blueprint SegmentedControl's `SegmentedControlOptionProps[]` type rejects
- **Fix:** Removed `as const` from OPTIONS array in AutonomyToggle.tsx
- **Files modified:** `src/frontend-react/src/panels/mission/AutonomyToggle.tsx`
- **Commit:** bb54e25

**2. [Rule 1 - Bug] ButtonGroup `small` prop doesn't exist in Blueprint5**
- **Found during:** Task 2 TypeScript check
- **Issue:** Blueprint5's `ButtonGroup` component doesn't expose a `small` prop
- **Fix:** Removed `small` from ButtonGroup in TransitionToast.tsx (Buttons themselves have `small`)
- **Files modified:** `src/frontend-react/src/panels/assets/TransitionToast.tsx`
- **Commit:** bb54e25

## Self-Check: PASSED

Files verified:
- `src/frontend-react/src/panels/mission/AutonomyToggle.tsx` — exists, contains SegmentedControl, set_autonomy_level
- `src/frontend-react/src/panels/assets/TransitionToast.tsx` — exists, contains approve_transition, reject_transition, setInterval
- `src/frontend-react/src/panels/assets/DroneModeButtons.tsx` — contains SUPPORT, VERIFY
- `src/frontend-react/src/panels/assets/DroneCard.tsx` — contains mode_source, TransitionToast
- `src/frontend-react/src/panels/mission/MissionTab.tsx` — contains AutonomyToggle
- `npx tsc --noEmit` — exits 0 (no type errors)

Commits verified:
- 62063d3 — feat(03-03): update types, store, and constants for autonomy system
- bb54e25 — feat(03-03): autonomy UI — AutonomyToggle, TransitionToast, updated DroneCard/ModeButtons
