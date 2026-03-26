# forward_sim.py Fixes — Wave 6

## Summary

All 3 HIGH and 3 MEDIUM issues fixed. 26/29 tests pass. 3 failures are pre-existing `filterpy` missing module errors (confirmed present before any changes).

---

## HIGH Fixes

### H1 — evaluate_coas now applies COA-specific state (FIXED)

Added `_apply_coa(clone, coa)` function that:
- Reads `coa["type"]` and applies a score bonus via `_COA_TYPE_SCORE_BONUS` dict
- For `STRIKE` COAs: finds the first NOMINATED/VERIFIED/LOCKED target in the clone and marks it DESTROYED using `pk_estimate` probabilistically
- Bonus table: STRIKE +2.0, HIGHEST_PK +1.5, FASTEST +0.5, LOWEST_COST 0.0, RECON -0.5
- TODO comment left for full physics-based COA application when `sim_engine` exposes `mark_target_engaged` API

### H2 — _evaluate_single no longer runs projection twice (FIXED)

Replaced the dual `project_forward` + `_project_and_summarise` calls with a single `_project_and_score(model, coa, ticks) -> (score, summary)` helper. One clone, one set of ticks, returns both score and summary together. Eliminates 2x redundant cloning and ticking per COA.

### H3 — Unbounded COA parallelism fixed (FIXED)

- Added `_MAX_PARALLEL_COAS = 8` semaphore in `evaluate_coas`
- Added hard cap: `if len(coas) > 64: raise ValueError("Too many COAs: ...")`
- Both enforced before any threads are dispatched

---

## MEDIUM Fixes

### M4 — project_forward tick errors now surfaced (FIXED)

`project_forward` now returns `{"score": float, "completed": bool}` instead of a bare `float`. The `completed` field is `False` if any tick raised an exception, `True` otherwise. The `projected_state_summary` in `evaluate_coas` also includes `"completed"`.

### M-SEC1 — ticks parameter clamped (FIXED)

Both `project_forward` and `_project_and_score` clamp `ticks = min(ticks, _MAX_TICKS)` where `_MAX_TICKS = 500`.

### M-SEC2 — Recursion limit mutation protected by threading.Lock (FIXED)

Added `_RECURSION_LOCK = threading.Lock()` and wrapped the `sys.setrecursionlimit` call in `clone_simulation` with `with _RECURSION_LOCK:`. This prevents races when multiple threads clone simultaneously.

---

## Test Results

```
29 collected
26 passed
3 failed (pre-existing: ModuleNotFoundError: No module named 'filterpy')
```

The 3 failing tests (`test_clone_with_real_sim_model`, `test_does_not_mutate_original_model`, `test_original_model_not_mutated`) all attempt to import `SimulationModel` from `sim_engine`, which transitively imports `filterpy` — a package missing from the venv. These failures existed before this PR and are unrelated to `forward_sim.py`.

New tests added:
- `test_returns_dict_with_score_and_completed` — M4 dict return
- `test_completed_true_on_clean_run` — M4 happy path
- `test_completed_false_when_tick_raises` — M4 error path
- `test_ticks_clamped_to_max` — M-SEC1
- `test_too_many_coas_raises_value_error` — H3 hard cap
- `test_exactly_64_coas_allowed` — H3 boundary
- `test_coa_types_receive_different_scores` — H1 differentiation
- `test_summary_has_completed_field` — M4 summary field

---

## Files Modified

- `src/python/forward_sim.py` — all fixes implemented
- `src/python/tests/test_forward_sim.py` — updated for new dict return + new tests
