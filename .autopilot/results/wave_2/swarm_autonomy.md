# W2-006: Swarm Coordinator Autonomy Awareness

## Status: COMPLETE

## Changes

### `src/python/swarm_coordinator.py`
- Added `SwarmRecommendation` frozen dataclass (uav_id, target_id, mode, reason, priority, autonomy_level)
- Modified `evaluate_and_assign()` to accept `autonomy_level` keyword argument (default: `"AUTONOMOUS"` for backward compatibility)
- **AUTONOMOUS** (default): executes assignments, updates `_active_tasks`, returns `TaskingOrder` list — unchanged behavior
- **SUPERVISED**: computes assignments but returns `SwarmRecommendation` list; does NOT update `_active_tasks`
- **MANUAL**: same as SUPERVISED — returns recommendations only
- **force=True**: bypasses autonomy gating (operator override always executes as `TaskingOrder`)
- Invalid `autonomy_level` raises `ValueError`

### `src/python/sim_engine.py`
- Periodic swarm tick (step 11) now passes `autonomy_level=self.autonomy_level` to `evaluate_and_assign()`
- Removed the "autonomy tier integration deferred" comment
- `request_swarm()` unchanged — operator override always executes via `force=True`

### `src/python/tests/test_swarm_autonomy.py` (NEW — 14 tests)
- `TestAutonomousMode` (3 tests): default returns TaskingOrders, backward compatible, updates active tasks
- `TestManualMode` (4 tests): returns SwarmRecommendation, no active task update, correct fields, frozen
- `TestSupervisedMode` (3 tests): returns SwarmRecommendation, no active task update, carries autonomy context
- `TestAutonomyEdgeCases` (4 tests): invalid level raises, force bypasses autonomy, empty targets handled

## Test Results
- 14 new tests: all passing
- 571 total tests: all passing (0 failures)
- Backward compatible: all existing swarm tests pass unchanged
