---
phase: 05-swarm-coordination
plan: "01"
subsystem: swarm-coordinator
tags: [tdd, swarm, sensor-fusion, greedy-algorithm, pure-logic]
dependency_graph:
  requires: [sensor_fusion.SensorContribution]
  provides: [SwarmCoordinator, SwarmTask, TaskingOrder, SENSOR_TYPES]
  affects: [sim_engine, api_main]
tech_stack:
  added: []
  patterns: [frozen-dataclass, greedy-assignment, idle-guard, priority-scoring]
key_files:
  created:
    - src/python/swarm_coordinator.py
    - src/python/tests/test_swarm_coordinator.py
  modified: []
decisions:
  - "Minimum 2 UAVs always reserved (min_idle_count=2 default) — fleet exhaustion guard"
  - "Idle guard checked before each assignment: idle_count <= min_idle_count means skip"
  - "already_assigned set initialized before target loop prevents duplicate UAV dispatch in one pass"
  - "SwarmTask.created_at uses field(default_factory=time.time) for 120s expiry"
  - "Auto-release triggered on VERIFIED/NOMINATED/LOCKED/ENGAGED/DESTROYED states"
  - "THREAT_WEIGHTS: SAM=1.0, TEL=0.9, RADAR=0.9, MANPADS/ARTILLERY=0.8, CP=0.7, APC/C2_NODE=0.6, TRUCK=0.5, LOGISTICS=0.3"
  - "Unknown target types default to THREAT_WEIGHTS 0.5"
  - "Tests use StubUAV/StubTarget — no sim_engine import, keeps tests pure and fast"
metrics:
  duration: "150s"
  completed_date: "2026-03-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
  tests_added: 11
  tests_passing: 398
---

# Phase 05 Plan 01: SwarmCoordinator Greedy Assignment Summary

**One-liner:** TDD'd `SwarmCoordinator` with greedy sensor-gap assignment, idle-count floor, 120s expiry, and auto-release on target state transitions — all in a pure-logic class with 11 passing unit tests.

## Tasks Completed

| Task | Type | Commit | Files |
|------|------|--------|-------|
| Task 1: RED — Write failing tests | test | 453fe4d | src/python/tests/test_swarm_coordinator.py |
| Task 2: GREEN + REFACTOR — Implement SwarmCoordinator | feat | f42e9e5 | src/python/swarm_coordinator.py |

## What Was Built

`src/python/swarm_coordinator.py` exports:

- `SENSOR_TYPES = ("EO_IR", "SAR", "SIGINT")` — module constant
- `SwarmTask` — frozen dataclass tracking target assignment, sensor coverage, and `created_at` timestamp
- `TaskingOrder` — frozen dataclass with uav_id, target_id, mode, reason, priority
- `SwarmCoordinator` — greedy coordinator class

### Algorithm: `evaluate_and_assign(targets, uavs) -> list[TaskingOrder]`

1. Expiry check: tasks older than 120s removed, SUPPORT UAVs released to SEARCH
2. Auto-release: targets in resolved states (VERIFIED through DESTROYED) release their fleet
3. Score DETECTED/CLASSIFIED targets with sensor gaps: `threat_weight * (1 - fused_confidence)`
4. Sort descending (highest urgency first)
5. Count idle (IDLE/SEARCH) UAVs
6. Greedy loop: for each gap sensor type per target, if `idle_count > min_idle_count`, find nearest eligible UAV and create TaskingOrder
7. `already_assigned` set prevents reassigning the same UAV twice in one pass
8. Update `_active_tasks` dict (preserve `created_at` for existing tasks)

### Tests: `src/python/tests/test_swarm_coordinator.py`

11 tests covering:
- `test_assigns_nearest_matching_uav` — nearer UAV selected over farther one
- `test_idle_guard_respected` — no orders when idle_count == min_idle_count
- `test_no_assignment_when_fully_covered` — all 3 sensor types covered, no orders
- `test_no_duplicate_sensor` — EO_IR already covered, only EO_IR UAVs available, no orders
- `test_priority_scoring` — SAM target assigned before TRUCK at same confidence
- `test_skips_rtb_repositioning` — RTB/REPOSITIONING UAVs excluded from assignment
- `test_multiple_gap_types` — 2 gap types produce 2 TaskingOrders
- `test_active_tasks_tracking` — `get_active_tasks()` reflects issued orders
- `test_swarm_task_is_frozen` — SwarmTask mutation raises FrozenInstanceError
- `test_tasking_order_is_frozen` — TaskingOrder mutation raises FrozenInstanceError
- `test_sensor_types_constant` — SENSOR_TYPES contains exactly EO_IR, SAR, SIGINT

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `src/python/swarm_coordinator.py` exists (221 lines, > 120 min)
- [x] `src/python/tests/test_swarm_coordinator.py` exists (236 lines, > 100 min)
- [x] Commit `453fe4d` exists (RED tests)
- [x] Commit `f42e9e5` exists (GREEN implementation)
- [x] 11/11 swarm coordinator tests pass
- [x] 398/398 full suite tests pass
- [x] SwarmTask and TaskingOrder are frozen dataclasses
- [x] SwarmTask has `created_at: float` with `field(default_factory=time.time)`
- [x] min_idle_count default = 2
- [x] Idle guard: `idle_count <= self.min_idle_count` checked before each assignment
- [x] `already_assigned: set[int]` initialized before target loop
- [x] 120-second expiry implemented
- [x] Auto-release on VERIFIED/NOMINATED/LOCKED/ENGAGED/DESTROYED
