# Cache get_state() Once Per Tick (W1-008)

## Summary
Compute `sim.get_state()` once at the top of `simulation_loop()` and pass the cached value to all consumers (broadcast, assessment, ISR queue) to eliminate 50-66% of the most expensive per-tick computation.

## Files to Modify
- `src/python/api_main.py` — In `simulation_loop()`, call `get_state()` once and pass result to broadcast, assessment thread, and ISR queue builder

## Files to Create
- `src/python/tests/test_get_state_caching.py` — Verify single call per tick

## Test Plan (TDD — write these FIRST)
1. `test_get_state_called_once_per_tick` — Mock `sim.get_state()` and verify it's called exactly once per simulation loop iteration
2. `test_cached_state_passed_to_broadcast` — The broadcast function receives the cached state dict
3. `test_cached_state_passed_to_assessment` — The assessment worker receives the cached state dict

## Implementation Steps
1. At the top of the tick body in `simulation_loop()`, add: `state = sim.get_state()`
2. Replace all subsequent `sim.get_state()` calls in the same tick with `state`
3. Pass `state` to `broadcast()`, assessment scheduling, and ISR queue builder
4. Verify `state` is a fresh snapshot each tick (not stale across ticks)

## Verification
- [ ] `grep -c "get_state()" src/python/api_main.py` shows exactly 1 call in the loop body
- [ ] 10Hz tick remains stable at 50 UAVs + 50 targets
- [ ] All existing tests pass

## Rollback
- Revert to multiple `get_state()` calls (restore original lines)
