# Input Validation on All WebSocket Actions (W1-013)

## Summary
Add validation for all raw WebSocket action parameters: coverage mode allowlist, lat/lon ranges, theater name allowlist, feed name allowlist, confidence bounds, SITREP query length.

## Files to Modify
- `src/python/api_main.py` — Add validation logic in `handle_payload()` for each action type that accepts user input

## Files to Create
- `src/python/tests/test_input_validation.py` — Comprehensive validation tests

## Test Plan (TDD — write these FIRST)
1. `test_coverage_mode_valid_accepted` — Valid coverage mode (OPERATIONAL, COVERAGE, etc.) accepted
2. `test_coverage_mode_invalid_rejected` — Invalid coverage mode string rejected with error
3. `test_lat_lon_valid_range_accepted` — lat in [-90,90], lon in [-180,180] accepted
4. `test_lat_lon_nan_rejected` — NaN lat/lon rejected
5. `test_lat_lon_inf_rejected` — Inf lat/lon rejected
6. `test_lat_out_of_range_rejected` — lat=91 rejected
7. `test_theater_name_in_allowlist_accepted` — Known theater name accepted
8. `test_theater_name_not_in_allowlist_rejected` — Unknown theater name rejected
9. `test_confidence_in_0_1_accepted` — Confidence 0.5 accepted
10. `test_confidence_out_of_range_rejected` — Confidence 1.5 rejected
11. `test_subscribe_feed_valid_accepted` — Known feed type accepted
12. `test_sitrep_query_length_limited` — Query over 500 chars rejected

## Implementation Steps
1. Create a validation helper module or inline validators in `handle_payload()`:
   ```python
   VALID_COVERAGE_MODES = {"OPERATIONAL", "COVERAGE", "THREAT", "FUSION", "SWARM", "TERRAIN"}
   VALID_FEED_TYPES = {"INTEL_FEED", "COMMAND_FEED", "SENSOR_FEED"}
   MAX_SITREP_LENGTH = 500
   ```
2. For each action in the dispatch chain, validate inputs before processing:
   - `set_coverage_mode`: check mode in allowlist
   - `move_drone`, `scan_area`, `place_waypoint`: validate lat/lon finite and in range
   - `SET_SCENARIO`: validate theater in `list_theaters()`
   - `subscribe`, `subscribe_sensor_feed`: validate feed name
   - `verify_target`: validate confidence in [0,1]
   - SITREP query: validate length
3. Return structured error JSON on validation failure

## Verification
- [ ] All WebSocket actions with user input have validation
- [ ] Invalid inputs return structured error (not crash or silent acceptance)
- [ ] All existing tests pass

## Rollback
- Remove validation checks from `handle_payload()`
