---
phase: 08-adaptive-isr-closed-loop
plan: 02
subsystem: adaptive-isr-integration
tags: [tdd, sim-engine, coverage-mode, isr-queue, heuristic, websocket]
dependency_graph:
  requires: [08-01]
  provides: [sim_engine.coverage_mode, sim_engine._threat_adaptive_dispatches, sim_engine.tasking_source, api_main.isr_queue_broadcast, api_main.set_coverage_mode_action, ai_tasking_manager._generate_response_heuristic]
  affects: [08-03]
tech_stack:
  added: []
  patterns: [threat-adaptive-dispatch, min-idle-guard, heuristic-fallback, ws-action-routing]
key_files:
  created: []
  modified:
    - src/python/sim_engine.py
    - src/python/api_main.py
    - src/python/agents/ai_tasking_manager.py
    - src/python/tests/test_adaptive_isr.py
decisions:
  - MIN_IDLE_COUNT = 3 guards threat-adaptive dispatch — never dispatches below 3 idle UAVs
  - set_coverage_mode validates against ('balanced', 'threat_adaptive') whitelist — silent reject on invalid
  - _threat_adaptive_dispatches mutates nearest.tasking_source='ISR_PRIORITY' and nearest.mode_source='AUTO' before returning dispatch list
  - SensorTaskingOrder (not plain dict) used in heuristic — ensures Pydantic validation round-trips cleanly
  - Heuristic uses asset.lat/asset.lon directly (not nested location object) — matches SensorAsset schema
  - ISR queue rebuilt every 5s inside the existing assessment block — no new timer needed
  - sim._last_assessment set after _cached_assessment is built — single data flow point
  - set_coverage_mode handler emits to COMMAND_FEED (consistent with other sim commands)
  - Python 3.9 requires Optional[dict] (not dict | None) for type hints
metrics:
  duration: 307s
  completed_date: "2026-03-20"
  tasks_completed: 2
  files_changed: 4
---

# Phase 08 Plan 02: Adaptive ISR Integration Summary

Wired Plan 01's pure ISR priority queue into the live simulation loop — coverage_mode toggle, threat-adaptive UAV dispatch respecting MIN_IDLE_COUNT, ISR queue rebuilt every 5s and broadcast over WebSocket, assessment passed to sim for dispatch decisions, and heuristic LLM-free fallback in AITaskingManagerAgent.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 RED | Failing tests for coverage_mode and threat-adaptive dispatch | 04447ee | test_adaptive_isr.py |
| 1 GREEN | coverage_mode, _threat_adaptive_dispatches, tasking_source in sim_engine | 1683c0d | sim_engine.py |
| 2 | WS action, ISR queue broadcast, heuristic tasking | 43617c1 | api_main.py, ai_tasking_manager.py, test_adaptive_isr.py |

## Decisions Made

**MIN_IDLE_COUNT = 3 fleet guard:** Threat-adaptive dispatch never reduces idle UAV count to zero — prevents scenario where all UAVs are tasked by assessment gaps leaving no reserve for new detections.

**Optional[dict] for Python 3.9:** `dict | None` union syntax requires Python 3.10+. Used `Optional[dict]` in `SimulationModel.__init__` for 3.9 compatibility.

**SensorTaskingOrder in heuristic:** The heuristic constructs proper `SensorTaskingOrder` Pydantic objects rather than plain dicts so `model_dump_json()` + `model_validate_json()` round-trips cleanly without schema mismatch.

**Single 5s assessment timer:** ISR queue build and `sim._last_assessment` assignment both happen inside the existing `if now - _last_assessment_time >= 5.0:` block — no separate timer or thread needed.

## Verification Results

```
src/python/tests/test_adaptive_isr.py - 31 passed in 0.76s
src/python/tests/ - 470 passed, 68 warnings in 19.16s (no regressions)
```

## Deviations from Plan

**[Rule 1 - Bug] Fixed Python 3.9 type hint incompatibility**
- Found during: Task 1 GREEN
- Issue: Plan spec used `dict | None` union syntax which requires Python 3.10+; project runs Python 3.9.6
- Fix: Changed to `Optional[dict]` in `SimulationModel.__init__`
- Files modified: src/python/sim_engine.py

**[Rule 1 - Bug] Fixed SensorTaskingOrder schema mismatch in heuristic**
- Found during: Task 2
- Issue: Plan spec showed plain dicts for tasking_orders but `TaskingManagerOutput.tasking_orders` is `List[SensorTaskingOrder]` — plain dicts fail Pydantic validation on `model_dump_json()` + `model_validate_json()` round-trip
- Fix: Constructed proper `SensorTaskingOrder` objects with all required fields (order_id, target_detection_id, estimated_collection_time_minutes, priority as int 1-5)
- Files modified: src/python/agents/ai_tasking_manager.py

**[Rule 1 - Bug] Fixed SensorAsset field access in heuristic**
- Found during: Task 2
- Issue: Plan spec used `asset.location.lat` / `asset.location.lon` but `SensorAsset` schema has `asset.lat` / `asset.lon` directly (no nested location object)
- Fix: Changed to `getattr(asset, 'lat', 0.0)` / `getattr(asset, 'lon', 0.0)`
- Files modified: src/python/agents/ai_tasking_manager.py

## Self-Check: PASSED
