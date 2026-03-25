# Re-apply Swarm Autonomy Changes

## Status: COMPLETE

## Changes Made

### `src/python/swarm_coordinator.py`
1. Added `SwarmRecommendation` frozen dataclass with fields: `uav_id`, `target_id`, `mode`, `reason`, `priority`, `autonomy_level`
2. Added `autonomy_level` parameter to `evaluate_and_assign()` (default `"AUTONOMOUS"` for backward compat)
3. Added `_VALID_AUTONOMY_LEVELS` class-level frozenset for validation
4. AUTONOMOUS mode: executes assignments and updates `_active_tasks` (existing behavior)
5. MANUAL/SUPERVISED mode: returns `SwarmRecommendation` list without updating `_active_tasks`
6. `force=True` bypasses autonomy gating — always returns `TaskingOrder` and executes
7. Invalid `autonomy_level` raises `ValueError`

### `src/python/sim_engine.py`
1. Imported `TaskingOrder` from `swarm_coordinator`
2. Periodic swarm tick now passes `autonomy_level=self.autonomy_level` to `evaluate_and_assign()`
3. Added `isinstance(order, TaskingOrder)` guard so recommendations are not executed as assignments

## Test Results
- `test_swarm_autonomy.py`: 14/14 passed
- Full suite: 571/571 passed, 0 failures
