# W2-005: Fix verify_target Handler Bypassing Verification Engine

## Status: COMPLETE

## Problem
The `verify_target` WebSocket action in `api_main.py` directly mutated `target.state = "VERIFIED"`, bypassing the `evaluate_target_state()` state machine in `verification_engine.py`. This meant:
- Sensor diversity and sustained-time requirements were ignored
- Only CLASSIFIED targets were handled (DETECTED targets silently ignored)
- No audit trail for operator overrides

## Changes

### `src/python/api_main.py`
1. Added `evaluate_target_state` to imports from `verification_engine`
2. Added `log_event` to imports from `event_logger`
3. Replaced the `verify_target` handler (lines ~1208-1236):
   - Now computes `sensor_type_count` from `target.sensor_contributions` (same logic as `sim_engine.py`)
   - Calls `evaluate_target_state()` with all required parameters including `demo_fast`
   - Only transitions state if the engine approves the new state
   - Logs `OPERATOR_OVERRIDE` event to audit trail via `log_event()` with `operator_override: True`
   - Sends error back to client if verification criteria not met (instead of silently ignoring)
   - Works for any state transition the engine allows (not just CLASSIFIED->VERIFIED)

### `src/python/tests/test_verify_target_handler.py` (new)
7 tests verifying:
- Engine promotes CLASSIFIED->VERIFIED when all criteria met
- Engine rejects low confidence
- Engine rejects insufficient sensors + time
- Sustained time alone can satisfy criteria
- DETECTED cannot jump directly to VERIFIED
- Terminal states are never changed
- `log_event` is importable and callable

## Test Results
- 571 tests passing (7 new + 564 existing)
- All existing tests unaffected

## Files Modified
- `src/python/api_main.py` (imports + verify_target handler)
- `src/python/tests/test_verify_target_handler.py` (new test file)
