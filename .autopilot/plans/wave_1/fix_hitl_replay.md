# Fix HITL Replay Attack (W1-012)

## Summary
Add `status == "PENDING"` check in `_transition_entry` to prevent REJECTED nominations from being replayed to APPROVED.

## Files to Modify
- `src/python/hitl_manager.py` — Add status check in `_transition_entry()` before allowing state transitions

## Files to Create
- `src/python/tests/test_hitl_replay.py` — Tests for replay prevention

## Test Plan (TDD — write these FIRST)
1. `test_pending_nomination_can_be_approved` — Normal flow: PENDING → APPROVED works
2. `test_rejected_nomination_cannot_be_approved` — REJECTED → APPROVED raises error or returns False
3. `test_approved_nomination_cannot_be_re_approved` — APPROVED → APPROVED idempotent or rejected
4. `test_replay_attempt_logged_as_security_event` — Non-PENDING transition attempt produces security log

## Implementation Steps
1. In `hitl_manager.py`, find `_transition_entry()` method
2. Add at the top:
   ```python
   if old.status != "PENDING":
       logger.warning("Security: attempted transition from %s status for entry %s", old.status, entry_id)
       return False  # or raise ValueError
   ```
3. Ensure callers handle the False/error return gracefully

## Verification
- [ ] Cannot approve a REJECTED nomination via WebSocket replay
- [ ] Security warning logged on replay attempt
- [ ] Normal PENDING → APPROVED/REJECTED flow works
- [ ] All existing tests pass

## Rollback
- Remove the status check from `_transition_entry()`
