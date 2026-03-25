# Fix Unbounded Memory Growth in TacticalAssistant (W1-007)

## Summary
Add pruning for `_nominated` set and `_prev_target_states` dict in TacticalAssistant to prevent unbounded memory growth during long demo sessions.

## Files to Modify
- `src/python/api_main.py` — Find `TacticalAssistant` class; add pruning logic to `_nominated` and `_prev_target_states`

## Files to Create
- `src/python/tests/test_tactical_assistant_memory.py` — Memory management tests

## Test Plan (TDD — write these FIRST)
1. `test_nominated_set_pruned_on_destroy` — Targets that are DESTROYED are removed from `_nominated`
2. `test_prev_states_pruned_for_missing_targets` — Targets no longer in sim are removed from `_prev_target_states`
3. `test_memory_stable_after_many_targets` — After processing 1000 targets (with destruction), both collections stay bounded

## Implementation Steps
1. In `TacticalAssistant`, find where `_nominated` is populated
2. Add cleanup: at the start of each evaluation cycle, compute `active_target_ids = {t.id for t in targets}` and prune `_nominated -= _nominated - active_target_ids`
3. Similarly prune `_prev_target_states`: `self._prev_target_states = {k: v for k, v in self._prev_target_states.items() if k in active_target_ids}`
4. Add the pruning call at the beginning of the method that processes targets each tick

## Verification
- [ ] `len(self._nominated)` stays ≤ number of active targets
- [ ] `len(self._prev_target_states)` stays ≤ number of active targets
- [ ] Demo runs 30+ minutes without memory growth in these collections
- [ ] All existing tests pass

## Rollback
- Remove the pruning lines from TacticalAssistant
