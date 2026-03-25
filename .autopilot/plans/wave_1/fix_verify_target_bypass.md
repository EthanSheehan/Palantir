# Fix verify_target Handler Bypassing Verification Engine (W1-013b)

## Summary
The `verify_target` WebSocket handler sets target state directly, bypassing the verification engine's state machine. Wire it through the verification engine instead.

## Files to Modify
- `src/python/api_main.py` — Change `verify_target` handler to call verification engine instead of setting state directly

## Files to Create
- `src/python/tests/test_verify_target_handler.py` — Tests for correct verification flow

## Test Plan (TDD — write these FIRST)
1. `test_verify_target_uses_engine` — Handler calls verification_engine, not direct state mutation
2. `test_verify_target_respects_thresholds` — Verification only advances if engine thresholds met
3. `test_verify_target_with_invalid_confidence` — Confidence outside [0,1] rejected (ties into W1-013)

## Implementation Steps
1. Find `verify_target` handler in `api_main.py`
2. Replace direct state assignment with call to verification engine's advance method
3. Pass the confidence value through the engine's threshold check

## Verification
- [ ] `verify_target` goes through verification engine state machine
- [ ] Thresholds are respected (can't skip CLASSIFIED→VERIFIED without meeting threshold)
- [ ] All existing tests pass

## Rollback
- Revert to direct state assignment in verify_target handler
