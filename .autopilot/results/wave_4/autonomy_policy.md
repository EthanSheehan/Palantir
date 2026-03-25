# W4-002: Per-Action Autonomy Matrix — Results

## Status: COMPLETE

## Files Created
- `src/python/autonomy_policy.py` — AutonomyPolicy class with immutable per-action levels, time-bounded grants, exception targets, force_manual, tick expiry
- `src/python/tests/test_autonomy_policy.py` — 40 tests covering all acceptance criteria

## Files Modified
- `src/python/sim_engine.py` — Added `autonomy_policy` field to SimulationModel.__init__
- `src/python/simulation_loop.py` — Added `policy.tick()` call each simulation tick to expire grants
- `src/python/websocket_handlers.py` — Added `set_action_autonomy` and `force_manual` actions; `set_autonomy_level` now syncs default level to policy

## Test Results
- 40/40 autonomy policy tests pass
- 1015/1015 full suite tests pass

## API Summary

### AutonomyPolicy
- `set_action_level(action, level, duration_seconds, exception_targets)` -> new policy (immutable)
- `get_action_level(action)` -> level (checks expiry)
- `get_effective_level(action, target_type)` -> level (checks exceptions)
- `set_default_level(level)` -> new policy
- `is_autonomous(action, target_type)` / `is_supervised(action, target_type)` -> bool
- `force_manual()` -> new policy (all MANUAL)
- `tick()` -> new policy (expired grants removed)
- `to_dict()` -> serializable dict for WebSocket broadcast

### WebSocket Actions
- `set_action_autonomy` — {action, level, duration_seconds?}
- `force_manual` — {} (emergency override)
- `set_autonomy_level` — backward compat, now also syncs policy default

### Valid Actions
FOLLOW, PAINT, INTERCEPT, AUTHORIZE_COA, ENGAGE, SWARM_ASSIGN
