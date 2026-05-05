# Fix SCANNING vs SEARCH Bug in Autopilot Dispatch (W1-001)

## Summary
Change invalid `"SCANNING"` mode string to `"SEARCH"` in autopilot dispatch and video simulator. This single-line bug silently breaks all autonomous target acquisition.

## Files to Modify
- `src/python/api_main.py` — Change `"SCANNING"` to `"SEARCH"` in `_find_nearest_available_uav()` (~line 275)
- `src/python/vision/video_simulator.py` — Change `"SCANNING"` to `"SEARCH"` (~line 198)

## Files to Create
- `src/python/tests/test_scanning_fix.py` — Tests for the SCANNING→SEARCH fix

## Test Plan (TDD — write these FIRST)
1. `test_find_nearest_uav_filters_search_mode` — Verify `_find_nearest_available_uav()` finds drones in SEARCH mode
2. `test_find_nearest_uav_ignores_non_search` — Verify drones in FOLLOW/PAINT/INTERCEPT are excluded
3. `test_autopilot_dispatches_search_drone_to_target` — Integration: demo_autopilot assigns a SEARCH drone when new target detected

## Implementation Steps
1. In `api_main.py`, find `_find_nearest_available_uav()` and replace `"SCANNING"` with `"SEARCH"`
2. In `video_simulator.py`, find the `"SCANNING"` reference and replace with `"SEARCH"`
3. Run full test suite to verify no regressions

## Verification
- [ ] `grep -r "SCANNING" src/python/` returns zero hits (excluding test assertions)
- [ ] `./grid_sentinel.sh --demo` shows drones dispatching to newly detected targets
- [ ] All 475 existing tests pass

## Rollback
- Revert the two string changes back to `"SCANNING"` (single-line changes)
