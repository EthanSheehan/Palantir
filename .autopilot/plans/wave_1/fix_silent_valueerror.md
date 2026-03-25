# Fix Silent ValueError Swallowing in Autopilot (W1-004)

## Summary
Replace all `except ValueError: pass` patterns in autopilot with `logger.exception()` and Intel Feed notifications so failures are visible.

## Files to Modify
- `src/python/api_main.py` — Replace 4 instances of `except ValueError: pass` (~lines 427, 498, 502, 507) with `logger.exception()` + Intel Feed event

## Files to Create
- (tests added to existing test files or `src/python/tests/test_valueerror_logging.py`)

## Test Plan (TDD — write these FIRST)
1. `test_coa_auth_failure_logged` — ValueError during COA authorization produces a log entry
2. `test_coa_auth_failure_intel_feed` — ValueError triggers an Intel Feed SAFETY/ERROR event
3. `test_autopilot_continues_after_valueerror` — Autopilot loop does not crash, continues to next iteration

## Implementation Steps
1. Find all `except ValueError: pass` in `api_main.py`
2. Replace each with:
   ```python
   except ValueError:
       logger.exception("COA authorization failed for target %s", target_id)
       # Optionally publish to Intel Feed
   ```
3. Ensure the autopilot loop continues after logging (no re-raise)

## Verification
- [ ] `grep -n "except ValueError: pass" src/python/api_main.py` returns zero hits
- [ ] Running demo with a forced ValueError shows log output
- [ ] All existing tests pass

## Rollback
- Revert the exception handler changes in `api_main.py`
