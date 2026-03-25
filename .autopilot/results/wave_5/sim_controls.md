# W5-001: Simulation Fidelity Controls — PASS

## Status: COMPLETE

## Deliverables

### New file: `src/python/sim_controller.py`
- `SimControlState` frozen dataclass (paused, speed_multiplier, step_requested)
- `SimController` class with immutable methods: `pause()`, `resume()`, `set_speed()`, `step()`, `consume_step()`
- `should_tick(base_dt)` returns `(should_run, effective_dt)`
- `get_state()` returns dict with paused, speed_multiplier, step_requested, valid_speeds
- `VALID_SPEEDS = frozenset({1, 5, 10, 50})`
- Invalid speed values raise `ValueError`

### New file: `src/python/tests/test_sim_controller.py`
- 32 tests, all passing
- Covers: pause/resume toggle, speed settings, invalid speed rejection, single-step mode, paused state blocks tick, get_state serialization

### Modified: `src/python/websocket_handlers.py`
- `SimController` imported from `sim_controller`
- `sim_controller` slot added to `HandlerContext`
- `_handle_sim_control` handler added (sub-actions: pause, resume, set_speed, step)
- `sim_control` registered in `_DISPATCH_TABLE`

### Modified: `src/python/simulation_loop.py`
- `get_sim_ctrl` optional callable parameter added to `simulation_loop()`
- When provided: checks pause/speed/step each tick, calls `sim.tick()` N times for speed compression, consumes step flag after single-step

### Modified: `src/python/api_main.py`
- `SimController` imported
- `sim_ctrl = SimController()` module-level instance
- `get_sim_ctrl=lambda: sim_ctrl` wired into `simulation_loop()` call
- `sim_controller=sim_ctrl` passed into `_build_handler_context()`

## Test Results
- `tests/test_sim_controller.py`: 32/32 passed
- `tests/test_websocket_handlers.py`: 69/69 passed
- `tests/test_sim_integration.py`: 24/24 passed
- Full suite (excluding pre-existing broken vision test): all passing

## Notes
- Linter revert partially hit `websocket_handlers.py` — `sim_controller` import and `_handle_sim_control` may need re-application if linter runs again
- Speed compression works by calling `sim.tick()` N times per loop interval (since `tick()` uses wall-clock dt internally)
