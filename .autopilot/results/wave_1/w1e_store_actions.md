---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# W1-E Store Actions — FIX-16 + FIX-13

## Status: PASS

---

## FIX-16: CoverageModeToggle optimistic update

**Problem:** Toggle sent WS message but didn't update store — UI snapped back until backend echo.

**Changes:**
- `SimulationStore.ts`: Added `setCoverageMode: (mode: string) => void` to interface and implementation — sets `coverageMode` in state immediately.
- `CoverageModeToggle.tsx`: `onValueChange` now calls `setCoverageMode(val)` before `sendMessage(...)`, so the UI updates instantly.

---

## FIX-13: Range button noop

**Problem:** Range button had `onClick={() => {}}` — completely inert.

**Changes:**
- `SimulationStore.ts`: Added `rangeRingDroneIds: number[]` state field (init `[]`) and `toggleRangeRing: (droneId: number) => void` action — toggles membership in the array.
- `DroneActionButtons.tsx`: Range button now calls `toggleRangeRing(uav.id)`. Button shows active state (amber border/background) when the drone's ID is in `rangeRingDroneIds`.

---

## Files modified

- `src/frontend-react/src/store/SimulationStore.ts`
- `src/frontend-react/src/panels/mission/CoverageModeToggle.tsx`
- `src/frontend-react/src/panels/assets/DroneActionButtons.tsx`

---

## Notes

- `rangeRingDroneIds` is pure UI state — Cesium range ring rendering can consume it via `useSimStore(s => s.rangeRingDroneIds)` when that layer is implemented.
- Coverage mode type is cast via `as 'balanced' | 'threat_adaptive'` to match existing `setSimData` pattern.
