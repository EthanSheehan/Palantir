---
phase: 02-target-verification-workflow
plan: 02
subsystem: sim_engine + api_main
tags: [verification, pipeline-gate, websocket, integration]
requirements: [FR-2, NFR-4]

dependency_graph:
  requires: [02-01]
  provides: [live-verification-promotion, isr-pipeline-gate, manual-verify-action]
  affects: [sim_engine.py, api_main.py, test_verification.py]

tech_stack:
  added: []
  patterns:
    - "Verification timer fields (time_in_state_sec, last_sensor_contact_time) on Target"
    - "demo_fast flag propagated from settings to SimulationModel"
    - "_last_verified dict pattern for one-shot pipeline trigger on state transition"

key_files:
  created: []
  modified:
    - src/python/sim_engine.py
    - src/python/api_main.py
    - src/python/tests/test_verification.py

decisions:
  - "Fade logic extended to CLASSIFIED/VERIFIED states (Rule 1 fix) — pre-existing test failed without it"
  - "_get_next_threshold is a method on SimulationModel (not module-level) to avoid forward-reference issues"
  - "Verification step skips DESTROYED/ENGAGED/ESCAPED targets to avoid spurious regressions"

metrics:
  duration: 233s
  completed: "2026-03-19"
  tasks: 2/2
  files: 3
---

# Phase 02 Plan 02: Verification Engine Wiring Summary

Wire the pure-function `verification_engine` (Plan 01) into the live simulation tick loop and gate the ISR nomination pipeline to only fire on VERIFIED targets.

## What Was Built

**sim_engine.py — full verification integration:**
- Added `from verification_engine import evaluate_target_state, VERIFICATION_THRESHOLDS, _DEFAULT_THRESHOLD`
- Extended `TARGET_STATES` tuple with `"CLASSIFIED"` and `"VERIFIED"` (between DETECTED and TRACKED)
- Added `time_in_state_sec: float = 0.0` and `last_sensor_contact_time: float = time.time()` to `Target.__init__`
- Added `self.demo_fast: bool = False` to `SimulationModel.__init__`
- Added `_get_next_threshold(self, target)` method on SimulationModel
- Wired `evaluate_target_state()` into `tick()` after the detection processing loop — runs once per non-terminal target per tick
- Extended fade logic from `state == "DETECTED"` to `state in ("DETECTED", "CLASSIFIED", "VERIFIED")` (deviation fix)
- Fixed `_assign_target` to allow `"CLASSIFIED"` and `"VERIFIED"` in the command guard
- Extended `get_state()` target payload with `time_in_state_sec`, `next_threshold`, `concealed`

**api_main.py — pipeline gate + manual verify:**
- `TacticalAssistant.__init__` adds `self._last_verified: dict = {}`
- `TacticalAssistant.update()` rewritten: NEW CONTACT fires on any non-UNDETECTED; ISR pipeline gate only fires when target transitions into VERIFIED (was_verified=False, is_verified=True)
- Added `"verify_target": {"target_id": "int"}` to `_ACTION_SCHEMAS`
- Added `elif action == "verify_target":` handler in `handle_payload()` — fast-tracks CLASSIFIED→VERIFIED with `log_event`
- Added `sim.demo_fast = settings.demo_mode` after `SimulationModel` instantiation

**test_verification.py — 9 new integration tests:**
- `TestSimIntegration`: timer fields exist, TARGET_STATES extended, get_state includes verification fields
- `TestPipelineGate`: `_last_verified` exists, gate does not fire on DETECTED, fires on VERIFIED
- `TestManualVerify`: `verify_target` in `_ACTION_SCHEMAS` with correct schema
- `TestBroadcast`: `next_threshold` correct for DETECTED (float), None for NOMINATED

## Test Results

- Pre-existing: 280 tests passing
- New integration tests: 9 tests added, all passing
- Final suite: **289 passed, 0 failed**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended fade logic to CLASSIFIED/VERIFIED states**
- **Found during:** Task 1 — test `test_confidence_degrades_on_removal` failed
- **Issue:** The fade/confidence-decay branch only checked `state == "DETECTED"`. After verification promotes targets to CLASSIFIED/VERIFIED, the decay never fired — existing integration test failed.
- **Fix:** Changed guard to `state in ("DETECTED", "CLASSIFIED", "VERIFIED")`
- **Files modified:** `src/python/sim_engine.py`
- **Commit:** 36a1e3c (included in Task 1 commit)

**2. [Rule 3 - Blocking] _get_next_threshold as method not module-level function**
- **Found during:** Task 1
- **Issue:** Plan specified a module-level `_get_next_threshold(target)` function, but it references `VERIFICATION_THRESHOLDS` and `_DEFAULT_THRESHOLD` which are already imported at module level. Made it a method on SimulationModel to keep consistent with where `get_state()` calls it.
- **Fix:** Implemented as `self._get_next_threshold(t)` method
- **No behavior difference**

## Self-Check

Files created/modified:
- [x] `src/python/sim_engine.py` — modified
- [x] `src/python/api_main.py` — modified
- [x] `src/python/tests/test_verification.py` — modified

Commits:
- [x] 36a1e3c — feat(02-02): wire verification_engine into sim_engine tick loop
- [x] ce28a60 — feat(02-02): gate ISR pipeline to VERIFIED, add verify_target action, integration tests

## Self-Check: PASSED
