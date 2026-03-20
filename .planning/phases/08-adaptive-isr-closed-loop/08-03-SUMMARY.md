---
phase: 08-adaptive-isr-closed-loop
plan: 03
subsystem: frontend-isr
tags: [react, ui, isr-queue, coverage-mode, tasking-badge]
dependency_graph:
  requires: [08-02]
  provides: [ISRQueue, CoverageModeToggle, tasking_source badge]
  affects: []
tech_stack:
  - react
  - typescript
  - blueprintjs
  - zustand
---

## Summary

Built the React frontend for the adaptive ISR closed loop: ISR queue table, coverage mode toggle, and per-drone tasking source badge.

## Tasks Completed

| # | Task | Status |
|---|------|--------|
| 1 | ISR types + store + ISRQueue + CoverageModeToggle + MissionTab wiring | ✓ |
| 2 | Tasking source badge on DroneCard | ✓ |
| 3 | Visual verification (human checkpoint) | ✓ Approved |

## Key Files

### Created
- `src/frontend-react/src/panels/mission/ISRQueue.tsx` — ISR priority queue table with urgency-colored tags
- `src/frontend-react/src/panels/mission/CoverageModeToggle.tsx` — Balanced/Threat-Adaptive segmented control

### Modified
- `src/frontend-react/src/store/types.ts` — Added ISRRequirement interface, tasking_source on UAV, isr_queue/coverage_mode on SimStatePayload
- `src/frontend-react/src/store/SimulationStore.ts` — Added isrQueue/coverageMode state fields and setSimData handling
- `src/frontend-react/src/panels/assets/DroneCard.tsx` — Added ISR/CMD tasking source badge
- `src/frontend-react/src/panels/mission/MissionTab.tsx` — Composed ISRQueue and CoverageModeToggle
- `src/python/api_main.py` — Added coverage_mode to WS broadcast payload (fix)

## Commits

- `0d24126` feat(08-03): add ISRQueue, CoverageModeToggle, ISR types and store fields
- `9875af0` feat(08-03): add tasking source badge to DroneCard
- `d8caaac` fix(08-03): broadcast coverage_mode in WS state payload

## Deviations

- **coverage_mode not broadcast**: The original Plan 02 implementation omitted broadcasting `coverage_mode` in the WS state payload. This caused the SegmentedControl toggle to appear unresponsive (it would fire the WS action but immediately reset on the next tick). Fixed by adding `state["coverage_mode"] = sim.coverage_mode` to the broadcast block in api_main.py.

## Self-Check: PASSED

- [x] ISRQueue.tsx renders table with target, type, urgency, gap, sensors columns
- [x] CoverageModeToggle sends set_coverage_mode WS action
- [x] DroneCard shows ISR/CMD badges for non-ZONE_BALANCE tasking
- [x] TypeScript compiles without errors
- [x] All Python tests pass (470+)
- [x] Human visual verification approved
