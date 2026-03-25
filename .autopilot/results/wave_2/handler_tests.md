# W2-004: Tests for handle_payload() and tactical_planner

## Status: COMPLETE

## Results

### test_websocket_handlers.py — 69 tests
- **_validate_payload**: 10 tests covering all type validators (int, float, str), missing fields, None fields, edge cases (float-as-int, fractional float)
- **_send_error**: 3 tests (JSON format, optional action field, disconnect swallowing)
- **handle_payload dispatch**: 6 tests (unknown action, validation rejection, type forwarding for DRONE_FEED/TRACK_UPDATE, SITREP_QUERY by type)
- **spike**: 1 test
- **move_drone**: 4 tests (valid, NaN, Inf, out-of-range coordinates)
- **follow_target/paint_target/intercept_target**: 3 tests (sim call + intel emit)
- **intercept_enemy**: 1 test
- **cancel_track/scan_area**: 2 tests (both share handler)
- **approve_nomination**: 2 tests (success + ValueError)
- **reject_nomination**: 2 tests (success + ValueError)
- **retask_nomination**: 1 test
- **authorize_coa**: 2 tests (success + ValueError)
- **reject_coa**: 1 test
- **reset**: 1 test
- **set_autonomy_level**: 2 tests (valid + invalid)
- **set_drone_autonomy**: 4 tests (not found, valid override, clear override, invalid level)
- **approve/reject_transition**: 2 tests
- **request/release_swarm**: 2 tests
- **set_coverage_mode**: 3 tests (balanced, threat_adaptive, invalid)
- **subscribe**: 4 tests (valid, invalid feed, non-list, history sent)
- **subscribe_sensor_feed**: 2 tests (valid, filters non-int)
- **sitrep_query**: 4 tests (basic, too long, non-string, generate_sitrep alias)
- **SET_SCENARIO**: 1 test (dispatch entry exists)
- **_build_sitrep_payload**: 4 tests (no targets, with targets, query included, query omitted)
- **dispatch table completeness**: 2 tests (schema→dispatch coverage, TYPE_FORWARD set)

### test_tactical_planner.py — 42 tests
- **_haversine_km**: 4 tests (zero distance, known distance, symmetry, antipodal)
- **_estimate_time_to_target**: 5 tests (time_to_effect field, rocket_flight_time, speed calc, zero speed, negative speed)
- **_score_asset**: 4 tests (all fields, pk, cost, default cost)
- **_compute_composite**: 5 tests (pk impact, time impact, risk impact, near-zero edge cases)
- **_risk_from_cost**: 3 tests (clamp low, clamp high, passthrough)
- **_build_coa**: 2 tests (correct fields, effector assignment)
- **_scored_to_hitl_coa**: 2 tests (frozen dataclass, composite positive)
- **_generate_coas_heuristic**: 3 tests (returns 3, sorted descending, all PROPOSED)
- **generate_coas (sync)**: 6 tests (skip non-Nominate, skip missing track, 3 COAs per nom, COA types, LLM fallback, multiple nominations)
- **generate_coas_enhanced (async)**: 6 tests (no adapter, unavailable adapter, LLM success, LLM exception, empty result, pk/risk clamping)
- **Agent init**: 2 tests

## Test Execution
```
111 passed in 1.17s
```

## Regression Check
Full suite run confirmed 0 new failures. 8 pre-existing failures in other test files (import errors for renamed/moved symbols like UAV_MODES, MAX_TURN_RATE, _ACTION_SCHEMAS).

## Files Created
- `src/python/tests/test_websocket_handlers.py`
- `src/python/tests/test_tactical_planner.py`
