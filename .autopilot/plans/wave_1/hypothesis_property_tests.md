# Hypothesis Property-Based Tests (W1-019)

## Summary
Add hypothesis property-based tests for critical simulation invariants: sensor fusion confidence bounds, verification no-regression, swarm no-dual-assignment, ISR priority ordering.

## Files to Modify
- `requirements.txt` — Add `hypothesis`

## Files to Create
- `src/python/tests/test_fusion_property.py` — Fusion invariant tests
- `src/python/tests/test_verification_property.py` — Verification invariant tests
- `src/python/tests/test_swarm_property.py` — Swarm assignment invariant tests
- `src/python/tests/test_isr_property.py` — ISR priority ordering tests

## Test Plan (TDD — write these FIRST)
1. `test_fusion_confidence_always_in_0_1` — For any valid sensor contributions, fused confidence ∈ [0,1]
2. `test_fusion_monotonic_with_more_sensors` — Adding sensors never decreases confidence
3. `test_fusion_empty_contributions_returns_zero` — No sensors → confidence 0
4. `test_verification_never_regresses_within_threshold` — State never goes backward (VERIFIED→CLASSIFIED) while thresholds are met
5. `test_verification_states_always_valid` — State is always one of the valid enum values
6. `test_swarm_no_dual_assignment` — No drone assigned to two targets simultaneously
7. `test_swarm_assignment_respects_capacity` — Number of assignments ≤ number of available drones
8. `test_isr_queue_sorted_descending` — ISR queue always sorted by priority score descending
9. `test_isr_scores_always_positive` — All ISR scores ≥ 0
10. `test_theater_bounds_contain_spawned_entities` — Generated positions within theater bounds

## Implementation Steps
1. Add `hypothesis>=6.0` to `requirements.txt`
2. Write `@given()` strategies for each domain:
   - Fusion: generate lists of `SensorContribution` with random confidences in [0,1]
   - Verification: generate target states and time deltas
   - Swarm: generate drone lists and target lists with random positions
   - ISR: generate target lists with random threat weights and verification states
3. Assert invariants hold for all generated inputs
4. Use `@settings(max_examples=200)` for reasonable CI runtime

## Verification
- [ ] All property tests pass with 200+ examples
- [ ] No invariant violations found
- [ ] CI runtime stays under 60s for property tests
- [ ] `hypothesis` importable in test environment

## Rollback
- Delete the 4 property test files; remove hypothesis from requirements
