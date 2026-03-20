---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 05
current_plan: 3
status: unknown
stopped_at: Completed 05-03-PLAN.md
last_updated: "2026-03-20T10:24:34.104Z"
progress:
  total_phases: 11
  completed_phases: 5
  total_plans: 37
  completed_plans: 21
---

# Project State

## Current Phase: 03-drone-modes-autonomy

## Position

- **Current Phase:** 05
- **Current Plan:** 3
- **Last Session:** 2026-03-20T10:24:34.101Z
- **Stopped At:** Completed 05-03-PLAN.md

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| 0: Foundation & React Migration | COMPLETE | All 8 plans done |
| 1: Multi-Sensor Fusion | COMPLETE | Plans 01+02+03 complete, UAT passed |
| 2: Verification Workflow | COMPLETE | Plans 01+02+03 complete, UAT 9/10 pass, 1 fixed |
| 3: Drone Modes & Autonomy | IN PROGRESS | Plan 01 complete — sim_engine modes + autonomy |
| 4: Enemy UAVs | PLANNED | |
| 5: Swarm Coordination | PLANNED | |
| 6: Information Feeds | PLANNED | |
| 7: Battlespace Assessment | PLANNED | |
| 8: Adaptive ISR | PLANNED | |
| 9: Map Modes | PLANNED | |
| 10: Drone Feeds | PLANNED | |

## Accumulated Context

### Roadmap Evolution

- Phase 4 inserted: enemy UAVs (old phases 4-9 renumbered to 5-10)

## Known Issues

- Theater YAML `speed_kmh`, `threat_range_km`, `detection_range_km` parsed but not consumed by sim

## Decisions Log

- 2026-03-19: tracked_by_uav_ids is command-managed only — detection loop does not mutate it
- 2026-03-19: Complementary fusion formula: max confidence per type, then 1-product(1-ci) across types
- 2026-03-19: sensor_count tracks raw contribution count (not deduplicated type count)
- 2026-03-19: fuse_detections() accepts Sequence (not just list) for forward compatibility
- 2026-03-19: fused_confidence only written when contributions present — prevents zeroing on empty detection ticks
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
- 2026-03-19: window.location.hostname in WS URL (not hardcoded localhost) for Vite proxy compatibility
- 2026-03-19: ViewerContext default { current: null } so consumers skip null-check on the ref
- 2026-03-19: WebSocketContext at App root mirrors vanilla state.ws without globals
- 2026-03-19: Window custom events (palantir:send, palantir:placeWaypoint, palantir:openDetailMap) bridge Cesium imperative hooks to React WebSocket context without prop drilling
- 2026-03-19: evaluate_target_state() is pure — takes state+evidence, returns new state string, never mutates input
- 2026-03-19: High-threat types (SAM/TEL/MANPADS) have lower verification thresholds (0.5/0.7) than default (0.6/0.8)
- 2026-03-19: DEMO_FAST halves time thresholds and lowers confidence by 0.1 (floor 0.3/0.4)
- 2026-03-19: Fade logic extended to CLASSIFIED/VERIFIED states — verification promotion broke pre-existing decay test
- 2026-03-19: ISR pipeline gate: only fires once per target on VERIFIED transition, tracked by _last_verified dict in TacticalAssistant
- 2026-03-19: useSendMessage() from App.tsx WebSocketContext is the correct pattern for leaf-component WS sends (consistent with DroneModeButtons)
- 2026-03-19: VerificationStepper onManualVerify only passed when state CLASSIFIED; component controls button render
- 2026-03-19: fused_confidence falls back to detection_confidence when Phase 1 sensor fusion hasn't run yet
- 2026-03-20: OVERWATCH mode does not require a tracked target — handled before target lookup in _update_tracking_modes()
- 2026-03-20: BDA auto-transition (timer-based) baked into BDA physics block — not routed through autonomy layer
- 2026-03-20: AUTONOMOUS_TRANSITIONS table at module level maps (mode, trigger) -> new_mode for 8 kill-chain events
- 2026-03-20: set_drone_autonomy accepts level=None to clear per-drone override (reverts to fleet-level autonomy_level)
- 2026-03-20: scan_area added to _ACTION_SCHEMAS — was handled but lacked schema validation for drone_id field
- 2026-03-20: Blueprint SegmentedControl requires mutable array options — as const incompatible
- 2026-03-20: TransitionToast renders inline (not OverlayToaster) — simpler countdown UI per research guidance
- 2026-03-20: EnemyUAV IDs start at 1000 to avoid collision with target IDs (0-30) and UAV IDs (0-19)
- 2026-03-20: JAMMING mode sets is_jamming=True enabling SIGINT detection via emitting=True gate
- 2026-03-20: EnemyUAV._turn_toward uses MAX_TURN_RATE without 3x multiplier (standard turn, no urgency)
- 2026-03-20: EVADING mode stubbed as RECON loiter — Plan 03 will implement actual evasion behavior
- 2026-03-20: ConstantPositionProperty used for enemy UAVs — no interpolation needed for adversarial entities
- 2026-03-20: enemy_uavs? optional in SimStatePayload for backward compat with pre-phase-04 backends
- 2026-03-20: ENM-{id-1000} display convention — enemy UAV IDs start at 1001 in backend
- 2026-03-20: Evasion triggers at fused_confidence > 0.5 with 15s cooldown — prevents mode thrashing
- 2026-03-20: Dwell kill holds UAV position (vx=vy=0) in close range zone for 3s to avoid orbit drift
- 2026-03-20: enemy_intercept_dispatched set in demo_autopilot prevents repeated dispatches per enemy UAV
- 2026-03-20: SwarmCoordinator min_idle_count=2 default — fleet exhaustion guard, checked before each assignment
- 2026-03-20: SwarmTask.created_at uses field(default_factory=time.time) for 120s expiry; frozen dataclass prevents mutation
- 2026-03-20: already_assigned set initialized before target loop prevents duplicate UAV dispatch in one evaluate_and_assign pass
- 2026-03-20: Auto-release triggered on target state VERIFIED/NOMINATED/LOCKED/ENGAGED/DESTROYED
- 2026-03-20: THREAT_WEIGHTS: SAM=1.0, TEL/RADAR=0.9, MANPADS/ARTILLERY=0.8, CP=0.7, APC/C2_NODE=0.6, TRUCK=0.5, LOGISTICS=0.3
- 2026-03-20: SwarmPanel uses React.memo with custom comparator on sensor coverage set and assigned_uav_ids length only — avoids re-rendering on 10Hz ticks
- 2026-03-20: PolylineDashMaterialProperty chosen over PolylineGlowMaterialProperty for swarm lines — semantic distinction from flow lines (glow)

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 00 | 01 | 1m 41s | 2/2 | 12 |
| 00 | 02 | ~2min | 2/2 | 5 |
| 00 | 05 | 4min | 2/2 | 9 |
| 01 | 01 | 2min | 1/1 | 2 |
| 00 | 06 | 10min | 2/2 | 13 |
| 01 | 02 | ~15min | 2/2 | 2 |
| Phase 01 P03 | 266s | 2 tasks | 8 files |
| Phase 02 P01 | 162 | 2 tasks | 2 files |
| Phase 02 P02 | 233s | 2 tasks | 3 files |
| Phase 02 P03 | 141 | 2 tasks | 4 files |
| Phase 03 P01 | 113s | 1 tasks | 2 files |
| Phase 03 P02 | 60s | 1 tasks | 1 files |
| Phase 03 P03 | 246s | 2 tasks | 8 files |
| Phase 04 P02 | 2 | 2 tasks | 7 files |
| Phase 04 P01 | 318 | 2 tasks | 3 files |
| Phase 04 P03 | 298 | 1 tasks | 5 files |
| Phase 05 P01 | 150 | 2 tasks | 2 files |
| Phase 05 P03 | 150 | 2 tasks | 6 files |
