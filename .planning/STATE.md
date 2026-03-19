# Project State

## Current Phase: 00-foundation-react-migration

## Position
- **Current Phase:** 00 - Foundation & React Migration
- **Current Plan:** 02 of 08 (Plan 01 complete)
- **Last Session:** 2026-03-19 — Completed 00-01-PLAN.md (type defs, Zustand store, React entry)
- **Stopped At:** 00-02-PLAN.md (next to execute)

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| 0: Foundation & React Migration | IN PROGRESS | Plan 01 complete |
| 1: Multi-Sensor Fusion | PLANNED | |
| 2: Verification Workflow | PLANNED | |
| 3: Drone Modes & Autonomy | PLANNED | |
| 4: Swarm Coordination | PLANNED | |
| 5: Information Feeds | PLANNED | |
| 6: Battlespace Assessment | PLANNED | |
| 7: Adaptive ISR | PLANNED | |
| 8: Map Modes | PLANNED | |
| 9: Drone Feeds | PLANNED | |

## Known Issues
- `sim_engine.py:509` — INTERCEPT mode missing from update exclusion list (double-update bug)
- Theater YAML `speed_kmh`, `threat_range_km`, `detection_range_km` parsed but not consumed by sim

## Decisions Log
- 2026-03-19: Full React + Blueprint migration (not hybrid)
- 2026-03-19: ECharts for charting (Palantir-style dark theme)
- 2026-03-19: Event logging (JSONL), not full sim replay
- 2026-03-19: Multi-sensor UAVs (some carry 2+), random distribution at spawn
- 2026-03-19: Selective Palantir repo adoption (Blueprint only)
- 2026-03-19: Skip Conjure, AtlasDB, Plottable, react-layered-chart
- 2026-03-19: Zustand for React state management
- 2026-03-19: Vite as build tool
- 2026-03-19: No StrictMode wrapper (Cesium Viewer double-mount breaks in StrictMode)
- 2026-03-19: Zustand v4 create() pattern locked at 4.5.0 (not v5 createStore)

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 00 | 01 | 1m 41s | 2/2 | 12 |
