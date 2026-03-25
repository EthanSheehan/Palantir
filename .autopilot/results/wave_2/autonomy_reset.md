# W2-008: Fix Autonomy Level Reset on Theater Switch

## Status: COMPLETE

## Problem
Theater switch via `POST /api/theater` recreated `SimulationModel`, resetting `autonomy_level` to `"MANUAL"` silently.

## Fix
In `api_main.py` `switch_theater()` endpoint (line ~914):
- Save `sim.autonomy_level` before creating new `SimulationModel`
- Restore it after creation
- Log WARNING when switching theaters with non-MANUAL autonomy

## Files Changed
- `src/python/api_main.py` — 3 lines added to `switch_theater()` endpoint
- `src/python/tests/test_autonomy_persistence.py` — new test file, 5 tests

## Tests
- 5 new tests in `test_autonomy_persistence.py` (all passing)
  - `test_autonomy_persists_after_theater_switch` — AUTONOMOUS survives switch
  - `test_autonomy_persists_supervised` — SUPERVISED survives switch
  - `test_manual_autonomy_persists` — MANUAL survives switch
  - `test_warning_logged_on_non_manual_theater_switch` — WARNING emitted
  - `test_no_warning_logged_on_manual_theater_switch` — no warning for MANUAL
- Full suite: 571 passed, 0 failed
