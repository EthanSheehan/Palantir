# WebSocket Message Size Guard (W1-011)

## Summary
Add a 64KB message size limit on incoming WebSocket messages before `json.loads()` to prevent trivial DoS.

## Files to Modify
- `src/python/api_main.py` — Add size check before `json.loads()` in the WebSocket message handler

## Files to Create
- `src/python/tests/test_websocket_size_guard.py` — Tests for oversized message rejection

## Test Plan (TDD — write these FIRST)
1. `test_message_under_64kb_accepted` — Normal-sized message processes correctly
2. `test_message_over_64kb_rejected` — 65KB message returns structured error, not parsed
3. `test_rejection_returns_error_response` — Error response includes reason and size limit

## Implementation Steps
1. In the WebSocket handler (where `data = await websocket.receive_text()` is called):
   ```python
   MAX_WS_MESSAGE_SIZE = 65536  # 64KB
   if len(data) > MAX_WS_MESSAGE_SIZE:
       await websocket.send_json({"error": "Message exceeds 64KB limit", "max_size": MAX_WS_MESSAGE_SIZE})
       continue
   ```
2. Add the constant to `config.py` or at module level
3. Place the check before `json.loads(data)`

## Verification
- [ ] Sending a 65KB+ WebSocket message returns error (not crash)
- [ ] Normal operations unaffected
- [ ] All existing tests pass

## Rollback
- Remove the size check lines
