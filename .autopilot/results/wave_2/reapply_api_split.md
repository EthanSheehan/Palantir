# Reapply api_main.py Split — Results

## Status: COMPLETE

## Problem
`build-split-sim` reverted api_main.py back to 1375 lines while splitting sim_engine.py, overwriting the slim orchestrator created by `build-split-api`.

## Resolution
Rewrote api_main.py as a slim orchestrator (~411 lines) that imports from the 4 extracted modules:
- `websocket_handlers.py` — command dispatch table, all action handlers, HandlerContext
- `simulation_loop.py` — simulation_loop(), sensor_feed_loop(), _serialize_assessment()
- `autopilot.py` — demo_autopilot() with dependency injection
- `tactical_assistant.py` — TacticalAssistant class, process_new_detection()

## Key Decisions

1. **Backward-compatible `handle_payload()`**: Tests call `api_main.handle_payload(payload, ws, raw_data)` with 3 args. The wrapper auto-builds a `HandlerContext` from module-level globals when `ctx` is not provided. Internal WebSocket endpoint uses `_ws_handle_payload` with explicit ctx.

2. **Module-level backward-compat exports**: Tests access `api_main.TacticalAssistant`, `api_main._ACTION_SCHEMAS`, `api_main._prev_target_states`, `api_main._last_assessment_time`, `api_main._cached_assessment`, `api_main._serialize_assessment`, `api_main.SimulationModel`. All re-exported via imports.

3. **`_prev_target_states` sharing**: `_loop_state.prev_target_states` dict is aliased as `api_main._prev_target_states` so tests that directly write to it still work.

4. **Autonomy persistence fix in `switch_theater()`**:
   - Saves `sim.autonomy_level` before creating new SimulationModel
   - Restores after creation
   - Logs WARNING via `logging.getLogger("api_main")` for non-MANUAL switches
   - All 5 autonomy persistence tests pass

## Test Results
- **557 passed**, 0 failed (ignoring `test_swarm_autonomy.py` which has pre-existing import error for `SwarmRecommendation`)
- **0 new test failures** introduced
