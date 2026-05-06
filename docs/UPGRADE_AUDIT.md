---
tags: [grid_sentinel, audit, upgrade_plan]
---
# UPGRADE_PLAN 9-Stage Implementation Audit

**Branch:** `worker/edith`
**Audit date:** 2026-05-06
**Repository:** `/Volumes/Toshiba_1TB/GitHub/Grid-Sentinel/`

## Summary table

| Stage | Title | Status | Evidence | Test file |
|-------|-------|--------|----------|-----------|
| 1 | Multi-Sensor Fusion | DONE | `sensor_fusion.py:28-51` (dataclasses), `:97-140` (fuse_detections), `target_behavior.py:88-90`, `sim_engine.py:506-523`, `:1088-1091` | `test_sensor_fusion.py` (190L) |
| 2 | Target Verification Workflow | DONE | `verification_engine.py:6-32` (4-state machine, per-type thresholds, regression timeouts) | `test_verification.py` + `test_verification_property.py` (528L total) |
| 3 | Drone Modes (MANUAL/SUPERVISED/AUTONOMOUS) | DONE | `autonomy_policy.py:12-102` (per-action autonomy, time-bounded grants) | `test_autonomy_policy.py`, `test_swarm_autonomy.py` (640+L) |
| 4 | Swarm Coordination & Tasking | DONE | `swarm_coordinator.py:21` (Hungarian), `:45-69` (dataclasses), `:267-280` (assign), `:174-200` (gap detection, expiry) | `test_swarm_coordinator.py`, `test_hungarian_swarm.py` (304+L) |
| 5 | Information Feeds | DONE | `intel_feed.py:17-50` (router), `:52-60` (subscription filter) | (integrated tests) |
| 6 | Battlespace Assessment | DONE | `battlespace_assessment.py:49-79` (frozen dataclasses), `:111-117` (assess), `:200-220` (clustering), `:259-289` (corridors) | `test_battlespace.py` (299L), `test_battlespace_manager.py` |
| 7 | Adaptive ISR / Closed-Loop Intelligence | DONE | `isr_priority.py:1-50` complete; `agents/ai_tasking_manager.py` now exposes `evaluate_and_retask_async()` routing through `LLMAdapter.complete_structured()` (Gemini → Anthropic → Ollama → heuristic). Sync path retains heuristic. | `test_adaptive_isr.py::TestAsyncTasking` |
| 8 | Map Modes & Tactical Views | DONE | `MapModeBar.tsx:7-12` (6 modes + shortcuts 1-6), `cesium/layers/use{Coverage,Fusion,Swarm,Threat,Terrain}Layer.ts` | (integrated) |
| 9 | Upgraded Drone Feeds | DONE | `types.ts:231` (4 SensorMode), `DroneCamPIP.tsx:4-70`, `SensorHUD.tsx:14-17`, `CamLayoutSelector.tsx:9-13` (SINGLE/PIP/SPLIT/QUAD), `vision/video_simulator.py:1-100` | (integrated) |

## Per-stage details

### Stage 1 — Multi-Sensor Target Fusion (DONE)

- `src/python/sensor_fusion.py:28-51` — `SensorContribution`, `FusedDetection`, `KalmanTrackState` frozen dataclasses
- `src/python/sensor_fusion.py:97-140` — `fuse_detections()` implements `1 - product(1-ci)` complementary fusion with per-sensor-type max deduplication
- `src/python/target_behavior.py:88-90` — Target has `tracked_by_uav_ids`, `sensor_contributions`, `fused_confidence`, `sensor_count`
- `src/python/sim_engine.py:506-523` — Detection loop accumulates contributions and fuses each tick
- `src/python/sim_engine.py:1088-1091` — WebSocket payload includes `fused_confidence`, `sensor_count`, `contributing_uav_ids`, `sensor_contributions`
- Tests: `src/python/tests/test_sensor_fusion.py` (190 lines)

### Stage 2 — Target Verification Workflow (DONE)

- `src/python/verification_engine.py:6-32` — `VerificationThreshold` dataclass, 4-state machine DETECTED → CLASSIFIED → VERIFIED → NOMINATED, per-type thresholds (SAM 0.5/0.7, TRUCK 0.6/0.8, etc.), regression timeouts 8–15s
- `src/python/verification_engine.py:44-100` — `evaluate_target_state()` pure function with `fused_confidence` thresholds, `sensor_type_count` requirements, sustained-time gates
- Tests: `test_verification.py` (352L) + `test_verification_property.py` (176L)

### Stage 3 — Drone Modes / Autonomy (DONE)

- `src/python/autonomy_policy.py:12` — `VALID_LEVELS = {"MANUAL", "SUPERVISED", "AUTONOMOUS"}`
- `src/python/autonomy_policy.py:12` — `VALID_ACTIONS = {"FOLLOW", "PAINT", "INTERCEPT", "AUTHORIZE_COA", "ENGAGE", "SWARM_ASSIGN"}`
- `src/python/autonomy_policy.py:17-102` — `AutonomyPolicy` with per-action overrides, time-bounded grants (`expires_at`), `exception_targets`
- Tests: `test_autonomy_policy.py` (319L), `test_swarm_autonomy.py`

**Variance from spec:** autonomy is per-action, not per-drone-mode. The 11 UAV modes (IDLE, SEARCH, FOLLOW, PAINT, INTERCEPT, SUPPORT, VERIFY, OVERWATCH, BDA, REPOSITIONING, RTB) exist as `uav.mode` strings but aren't a formal enum.

### Stage 4 — Swarm Coordination (DONE)

- `src/python/swarm_coordinator.py:21` — `scipy.optimize.linear_sum_assignment` (Hungarian algorithm)
- `src/python/swarm_coordinator.py:45-69` — `SwarmTask`, `TaskingOrder`, `SwarmRecommendation` dataclasses
- `src/python/swarm_coordinator.py:267-280` — `_hungarian_assign()` builds cost matrix and assigns
- `src/python/swarm_coordinator.py:174-200` — sensor-gap detection, 120s task expiry, idle-count guard, Byzantine anomaly check
- Tests: `test_swarm_coordinator.py` (304L), `test_hungarian_swarm.py`

### Stage 5 — Information Feeds (DONE)

- `src/python/intel_feed.py:17-50` — `IntelFeedRouter` with `emit()`, `get_history()`, broadcast integration
- `src/python/intel_feed.py:52-60` — `_client_subscribed()` subscription filtering (legacy clients get all, subscribed clients get filtered)
- Feed types: `INTEL_FEED`, `COMMAND_FEED`, `SENSOR_FEED`

### Stage 6 — Battlespace Assessment (DONE)

- `src/python/battlespace_assessment.py:49-79` — `ThreatCluster`, `CoverageGap`, `MovementCorridor`, `AssessmentResult` frozen dataclasses
- `src/python/battlespace_assessment.py:111-117` — `BattlespaceAssessor.assess()` computes clusters, coverage gaps, zone threat scores, movement corridors as a single frozen result
- `:200-220` — KDTree-based clustering
- `:259-289` — `_detect_movement_corridors()` position-history analysis
- Tests: `test_battlespace.py` (299L), `test_battlespace_manager.py`, `test_battlespace_manager_impl.py`

**Variance from spec:** clustering and corridor detection are integrated into `BattlespaceAssessor` rather than standalone `dbscan_clustering.py` / `corridor_detection.py` modules.

### Stage 7 — Adaptive ISR / Closed-Loop Intelligence (DONE)

- `src/python/isr_priority.py:1-50` — `ISRRequirement` dataclass, `THREAT_WEIGHTS` dict, `build_isr_queue()` function
- `src/python/agents/ai_tasking_manager.py` — `evaluate_and_retask_async()` routes through `LLMAdapter.complete_structured()` (Gemini → Anthropic → Ollama → heuristic). Sync `evaluate_and_retask()` retains heuristic-only behaviour for legacy callers; the obsolete `NotImplementedError` is gone.
- `src/python/api_main.py:103` now passes `llm_adapter` to the agent so the websocket `retask_sensors` handler picks up the async path automatically.
- `src/python/websocket_handlers.py:506` awaits `evaluate_and_retask_async`.
- Tests: `test_adaptive_isr.py::TestAsyncTasking` covers LLM hit, empty-LLM fallback, no-client fallback, and threshold short-circuit.

### Stage 8 — Map Modes & Tactical Views (DONE)

- `src/frontend-react/src/overlays/MapModeBar.tsx:7-12` — 6 modes: OPERATIONAL, COVERAGE, THREAT, FUSION, SWARM, TERRAIN with shortcuts 1–6
- `src/frontend-react/src/store/types.ts:192` — `MapMode` enforces 6 modes
- 5 layer overlays under `cesium/layers/`: `useCoverageLayer.ts`, `useFusionLayer.ts`, `useSwarmLayer.ts`, `useThreatLayer.ts`, `useTerrainLayer.ts` (OPERATIONAL is base)

### Stage 9 — Upgraded Drone Feeds (DONE)

- `src/frontend-react/src/store/types.ts:231` — `SensorMode = 'EO_IR' | 'SAR' | 'SIGINT' | 'FUSION'`
- `DroneCamPIP.tsx:4-70` — multi-layout PIP rendering sensor canvas + SensorHUD + mode toggle
- `CamLayoutSelector.tsx:9-13` — SINGLE / PIP / SPLIT / QUAD layouts
- `SensorHUD.tsx:1-60` — color-coded per sensor type (EO_IR #4A90E2, SAR #7ED321, SIGINT #F5A623, FUSION #00ffff)
- `src/python/vision/video_simulator.py:1-100` — `gps_to_pixel`, target rendering per type (SAM diamond, TEL triangle, etc.)

## Test coverage summary

- 75 test files in `src/python/tests/`
- Stage 1: `test_sensor_fusion.py` (190L)
- Stage 2: `test_verification.py` (352L) + `test_verification_property.py` (176L)
- Stage 3: `test_autonomy_policy.py` (319L)
- Stage 4: `test_swarm_coordinator.py` (304L)
- Stage 6: `test_battlespace.py` (299L)

## Key findings

**All 9 stages fully implemented** as of 2026-05-06 after wiring `ai_tasking_manager.py` to the LLMAdapter. Heuristic fallback remains for offline operation.

**Minor variances from spec:**
- Stage 3: autonomy is per-action, not per-drone-mode
- Stage 6: clustering and corridor detection integrated into `BattlespaceAssessor`, not standalone modules
- Stage 8: 5 overlays + base operational layer = effective 6-mode system

**No critical gaps.** All dataclasses, fusion formulas, state machines, swarm algorithms, WebSocket payloads, and frontend components are present and non-stubbed. Stage 7's heuristic tasking path is viable pending LLM integration.

## Track B closeout

Stage 7 has been wired (see `feat: Stage 7 — adaptive ISR via LLMAdapter` commit). Out of scope for this round: standalone `dbscan_clustering.py` / `corridor_detection.py` extraction (current integrated form works); formal `autonomy_matrix.py` mode-level enum (current per-action policy works).
