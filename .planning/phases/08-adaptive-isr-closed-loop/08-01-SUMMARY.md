---
phase: 08-adaptive-isr-closed-loop
plan: 01
subsystem: isr-priority
tags: [tdd, pure-function, isr, priority-queue, scoring]
dependency_graph:
  requires: []
  provides: [isr_priority.build_isr_queue, isr_priority.ISRRequirement, isr_priority.THREAT_WEIGHTS]
  affects: [08-02, 08-03]
tech_stack:
  added: []
  patterns: [frozen-dataclass, pure-function, threat-weighted-scoring]
key_files:
  created:
    - src/python/isr_priority.py
    - src/python/tests/test_adaptive_isr.py
  modified: []
decisions:
  - ISRRequirement frozen dataclass (immutable, safe for caching and comparison)
  - urgency = threat_weight * (1 - fused_confidence) * (0.5 + 0.5 * min(1.0, time_in_state_sec / 60.0))
  - ALL_SENSOR_TYPES = frozenset({"EO_IR", "SAR", "SIGINT"}) — closed set for missing sensor computation
  - EXCLUDED_STATES = frozenset({"DESTROYED", "ESCAPED", "UNDETECTED"}) — terminal and pre-detection states filtered
  - Only IDLE UAVs recommended — avoids pulling UAVs off active tasks
  - assessment_result accepted but not consumed in Plan 01 — reserved for Plan 02 weighting
metrics:
  duration: 109s
  completed_date: "2026-03-20"
  tasks_completed: 1
  files_changed: 2
---

# Phase 08 Plan 01: ISR Priority Queue Builder Summary

Pure-function ISR priority queue that ranks targets by threat_weight * verification_gap * time_factor, returning a sorted list of frozen ISRRequirement dataclasses ready for adaptive sensor tasking.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 RED | Failing tests for ISR priority queue | 6d38607 | test_adaptive_isr.py |
| 1 GREEN | ISR priority queue implementation | c2e8ddb | isr_priority.py |

## Decisions Made

**urgency scoring formula:** `threat_weight * (1 - fused_confidence) * (0.5 + 0.5 * min(1.0, time_in_state_sec / 60.0))` — ensures a target at time=0 gets half the time-bonus, ramping to full at 60s. Prevents cold-start targets from appearing falsely urgent.

**EXCLUDED_STATES pattern:** Mirrors `verification_engine.py` module-level frozenset constant style. UNDETECTED excluded because the ISR loop should not attempt to task UAVs toward targets that haven't been detected yet.

**assessment_result parameter:** Accepted but not consumed in Plan 01. Signature is forward-compatible — Plan 02 will weight urgency_score by zone threat scores from the assessment dict.

**Sensor recommendation filters:** Only IDLE UAVs, only those carrying at least one missing sensor type. Sorted by Euclidean lon/lat distance (sufficient precision at theater scale).

## Verification Results

```
src/python/tests/test_adaptive_isr.py - 16 passed in 0.03s
src/python/tests/ - 455 passed, 68 warnings in 17.70s (no regressions)
```

## Deviations from Plan

None — plan executed exactly as written. 16 tests (4 more than the 12 listed in the plan spec) were written to achieve comprehensive coverage including `test_verification_gap_field`, `test_assessment_result_accepted`, `test_recommended_uav_ids_idle_only`, and `test_returns_isrrequirement_instances`.

## Self-Check: PASSED
