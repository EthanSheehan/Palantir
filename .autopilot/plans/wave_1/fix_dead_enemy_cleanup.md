# Fix Dead Enemy Cleanup Branch / Memory Leak (W1-002)

## Summary
Fix unreachable `"DESTROYED"` branch in enemy UAV processing loop and add pruning for unbounded `enemy_intercept_dispatched` set.

## Files to Modify
- `src/python/api_main.py` — Restructure enemy UAV loop: move DESTROYED cleanup before the `continue` guard (~line 307-323), add pruning of `enemy_intercept_dispatched` when enemies are destroyed

## Files to Create
- (tests added to `src/python/tests/test_enemy_cleanup.py`)

## Test Plan (TDD — write these FIRST)
1. `test_destroyed_enemy_removed_from_dispatch_set` — After enemy is destroyed, its ID is removed from `enemy_intercept_dispatched`
2. `test_dispatch_set_bounded_after_many_enemies` — Set size stays bounded after spawning and destroying many enemies
3. `test_destroyed_branch_reachable` — DESTROYED enemies are actually processed (not skipped)

## Implementation Steps
1. In the enemy UAV loop in `api_main.py`, move the `DESTROYED` check before the `continue` on line 307
2. In the DESTROYED branch, remove the enemy ID from `enemy_intercept_dispatched`
3. Optionally add a TTL/cap on `enemy_intercept_dispatched` as a safety net

## Verification
- [ ] `enemy_intercept_dispatched` size stays bounded during 30-min demo
- [ ] Enemy UAVs that are destroyed can be re-intercepted if new enemies spawn with same ID pattern
- [ ] All existing tests pass

## Rollback
- Revert the loop restructuring in `api_main.py`
