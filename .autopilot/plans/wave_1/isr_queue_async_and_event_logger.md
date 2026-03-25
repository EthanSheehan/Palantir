# Move build_isr_queue() to Assessment Thread + Fix Event Logger (W1-010)

## Summary
Move `build_isr_queue()` off the main event loop into the async assessment worker, and fix the event logger to keep its file handle open instead of opening/closing on every write.

## Files to Modify
- `src/python/api_main.py` — Move `build_isr_queue()` call into the `asyncio.to_thread()` assessment worker
- `src/python/event_logger.py` — Refactor to keep file handle open; flush periodically instead of open/close per write

## Files to Create
- `src/python/tests/test_event_logger_perf.py` — Tests for persistent file handle

## Test Plan (TDD — write these FIRST)
1. `test_isr_queue_runs_in_thread` — Verify `build_isr_queue()` executes in assessment thread, not main loop
2. `test_event_logger_keeps_handle_open` — File handle is opened once and reused across multiple writes
3. `test_event_logger_flushes_periodically` — Data is flushed to disk at regular intervals
4. `test_event_logger_handles_rotation` — File rotation still works with persistent handle

## Implementation Steps
1. In `api_main.py`, find where `build_isr_queue()` is called synchronously (every 5s)
2. Move it into the existing `asyncio.to_thread()` block that runs assessment
3. In `event_logger.py`, refactor the `log()` method:
   - Open file handle in `__init__()` or on first write
   - Keep handle as instance variable
   - Write + flush on each log call (or buffer with periodic flush)
   - Handle daily rotation by checking date and reopening when needed
4. Add `__del__` or context manager to close handle on shutdown

## Verification
- [ ] No synchronous `build_isr_queue()` call on the event loop
- [ ] Event logger file handle opened once per rotation period
- [ ] 10Hz loop not blocked by ISR or logging
- [ ] All existing tests pass

## Rollback
- Move `build_isr_queue()` back to synchronous call; revert event_logger to open/close pattern
