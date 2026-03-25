# W2-002: Split api_main.py God File — Results

## Status: COMPLETE

## Changes Made

### Extracted Modules

| Module | Lines | Contents |
|--------|-------|----------|
| `websocket_handlers.py` | 547 | Command dispatch table (dict), all action handlers, `_ACTION_SCHEMAS`, `_validate_payload`, `_send_error`, `_build_sitrep_payload`, `HandlerContext` |
| `simulation_loop.py` | 227 | `simulation_loop()`, `sensor_feed_loop()`, `_serialize_assessment()`, `SimulationLoopState` class |
| `autopilot.py` | 335 | `demo_autopilot()` decoupled from globals — accepts injected `sim`, `hitl`, `broadcast_fn`, `clients`, `intel_router`, `tactical_planner`, `get_effectors` |
| `tactical_assistant.py` | 151 | `TacticalAssistant` class, `process_new_detection()` |

### api_main.py Reduction
- **Before:** 1,375 lines
- **After:** 325 lines (76% reduction)
- **Remaining:** app setup, FastAPI routes, WebSocket endpoint, broadcast(), lifespan, agent instantiation

### Key Improvements

1. **Command dispatch table** (F-011): 200-line if/elif chain replaced with `_DISPATCH_TABLE` dict in `websocket_handlers.py`
2. **Decoupled autopilot**: `demo_autopilot()` accepts all dependencies via keyword args — testable with AsyncMock
3. **asyncio.to_thread data race**: State snapshotted (copied) before thread dispatch in `simulation_loop.py`
4. **broadcast() logs client ID** on removal for debugging
5. **_process_new_detection() uses logger.exception()** instead of `str(exc)`
6. **Demo delays configurable**: `approval_delay`, `follow_delay`, `paint_delay` params on `demo_autopilot()`
7. **Backward compatibility**: `handle_payload()` in api_main auto-builds ctx if not provided — existing tests unmodified

## Test Results
- **568 passed**, 3 failed (pre-existing autonomy persistence failures, confirmed on main branch)
- **0 new test failures** introduced by this refactor
