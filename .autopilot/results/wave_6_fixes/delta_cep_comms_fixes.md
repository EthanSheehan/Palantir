# Wave 6 Fixes: delta_compression, cep_model, comms_sim

## Status: ALL TESTS PASS (134/134)

---

## HIGH Fixes

### delta_compression.py — Unbounded recursion (lines 16, 89)
- Added `_depth: int = 0` parameter to `compute_delta()` and `apply_delta()`
- Both functions raise `ValueError("State nesting too deep")` at `_depth > 50`
- `_diff_list()` also receives and propagates `_depth` when calling `compute_delta()`

### cep_model.py — Sequential seeds in Monte Carlo (lines 147-160)
- `estimate_pk()` no longer calls `simulate_engagement()` with sequential seeds 0,1,2,...
- Now creates a single `random.Random` instance seeded from `os.urandom(4)` by default
- Added optional `seed` parameter (default `None`) for explicit reproducibility
- All n_samples drawn from the same RNG instance — true Monte Carlo behavior

---

## MEDIUM Fixes

### delta_compression.py — `__deleted__` sentinel collision
- Added `_DELETED_SENTINEL = object()` identity sentinel for internal comparisons
- Serialized wire format still uses `"__deleted__"` string for JSON compatibility
- External API (tests) unchanged

### delta_compression.py — `_list_has_ids` only checks `lst[0]`
- Now checks up to first 3 items: `all(isinstance(lst[i], dict) and "id" in lst[i] for i in range(min(3, len(lst))))`
- Prevents false positives from mixed lists

### delta_compression.py — `apply_delta` shallow copy
- Changed `result = dict(base_state)` to `result = copy.deepcopy(base_state)`
- Changed `result_by_id` in `_apply_list_delta` to use `copy.deepcopy(item)` instead of `copy.copy(item)`

### comms_sim.py — `degrade_all_links(factor=0)` ZeroDivisionError
- Added guard: `if factor <= 0: raise ValueError(f"factor must be > 0, got {factor}")`

### comms_sim.py — `attempt_delivery` uses global random
- Added optional `rng: Optional[random.Random] = None` parameter
- Uses `rng.random()` when provided, falls back to `random.random()` otherwise

### cep_model.py — `lethal_radius=0` ZeroDivisionError
- Added module-load validation loop over `WEAPON_PROFILES`
- Raises `ValueError` if any profile has `lethal_radius <= 0`

---

## Test Results

```
134 passed in 0.25s
- test_delta_compression.py: 40 passed
- test_cep_model.py: 37 passed
- test_comms_sim.py: 57 passed
```
