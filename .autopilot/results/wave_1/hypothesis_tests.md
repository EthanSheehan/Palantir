# W1-019: Hypothesis Property-Based Tests — Results

## Status: PASS

**Date:** 2026-03-21
**Runtime:** ~42s for 22 tests (200 examples each = ~4400 total generated cases)

## Test Files Created

| File | Tests | Status |
|------|-------|--------|
| `src/python/tests/test_fusion_property.py` | 6 | PASS |
| `src/python/tests/test_verification_property.py` | 5 | PASS |
| `src/python/tests/test_swarm_property.py` | 5 | PASS |
| `src/python/tests/test_isr_property.py` | 6 | PASS |
| **Total** | **22** | **22/22 PASS** |

## Invariants Verified

### Sensor Fusion (`fuse_detections`)
- `test_fusion_confidence_always_in_0_1` — fused_confidence ∈ [0, 1] for all inputs
- `test_fusion_monotonic_with_more_sensors` — adding sensors never decreases confidence
- `test_fusion_empty_contributions_returns_zero` — empty input → 0.0 confidence
- `test_fusion_single_contribution` — single sensor returns its own confidence exactly
- `test_fusion_sensor_types_in_result` — result sensor types are a subset of input types
- `test_fusion_uav_ids_subset_of_input` — result UAV IDs are a subset of input IDs

### Verification Engine (`evaluate_target_state`)
- `test_terminal_states_never_change` — NOMINATED/LOCKED/ENGAGED/DESTROYED/ESCAPED are immutable
- `test_output_state_is_always_valid` — output is always a known valid state string
- `test_no_regression_below_timeout` — no regression when seconds_since_sensor = 0
- `test_state_transitions_are_deterministic` — same inputs always produce same output
- `test_verified_can_be_reached_from_classified_with_enough_evidence` — VERIFIED achievable with 0.8+ confidence, 3+ sensors, 30+ seconds

### Swarm Coordinator (`evaluate_and_assign`)
- `test_no_dual_assignment` — no drone assigned to 2+ targets in one call
- `test_assignment_count_respects_available_drones` — assignments ≤ assignable drones
- `test_assigned_uav_ids_exist_in_input` — all assigned UAV IDs are from input
- `test_assigned_target_ids_exist_in_input` — all assigned target IDs are from input
- `test_force_flag_still_no_dual_assignment` — no dual assignment with force=True

### ISR Priority (`build_isr_queue`)
- `test_isr_queue_sorted_descending` — queue always sorted by urgency_score descending
- `test_isr_scores_always_non_negative` — all urgency scores ≥ 0
- `test_isr_queue_length_capped` — output length ≤ max_requirements
- `test_excluded_states_not_in_queue` — DESTROYED/ESCAPED/UNDETECTED targets excluded
- `test_verification_gap_in_0_1` — verification_gap ∈ [0, 1]
- `test_active_targets_may_appear_in_queue` — only active targets in returned queue

## No Invariant Violations Found

Zero failures across all 4400+ generated test cases. No edge cases triggered assertion failures.

## Pre-existing Test Suite

The pre-existing failures (test_feeds.py, test_hitl_manager.py, test_sim_integration.py) are caused by missing `fastapi`/`structlog` in the system Python interpreter — these are pre-existing environment issues unrelated to this work. All non-FastAPI tests continue to pass.
