# corridor_detection.py — Wave 6 Fix Results

## Status: COMPLETE — 33/33 tests pass

## Fixes Applied

### MEDIUM — _heading_deg wrong axis order (CORRECTNESS BUG)
**File:** `src/python/corridor_detection.py` line 103-110
**Fix:** Changed `atan2(dy, dx)` to `atan2(dx, dy)` for correct compass bearing (east=90°, north=0°).
Comments updated to clarify `dx` = east (longitude delta), `dy` = north (latitude delta).
**Test impact:** No tests broke — existing assertions only checked `heading_deg >= 0.0`, not specific values.

### MEDIUM — douglas_peucker unbounded recursion
**File:** `src/python/corridor_detection.py`
**Fix:** Added `_MAX_HISTORY_POINTS = 500` constant. In `_process_target`, points are truncated to `[:_MAX_HISTORY_POINTS]` before calling `douglas_peucker`, bounding recursion depth to ~log2(500) ≈ 9 levels.

### MEDIUM — _extract_points null-island fallback
**File:** `src/python/corridor_detection.py` line ~296
**Fix:** Replaced `entry.get("lon", entry.get("x", 0.0))` pattern with try/except block. Entries with missing keys (None), non-numeric values, or non-finite floats (NaN/Inf) are now silently skipped rather than silently contributing (0.0, 0.0) null-island coordinates.

### MEDIUM — target_histories unbounded
**File:** `src/python/corridor_detection.py`
**Fix:** Added `_MAX_TARGETS = 200` constant. `detect_corridors` now takes `list(items)[:_MAX_TARGETS]` before iteration.

### MEDIUM — detect_corridors is 69 lines
**File:** `src/python/corridor_detection.py`
**Fix:** Extracted `_process_target(target_id, history, epsilon_deg, min_consistency) -> Optional[Corridor]` helper. `detect_corridors` is now ~20 lines; `_process_target` handles all per-target logic.

### LOW — corridor_id unsanitized
**File:** `src/python/corridor_detection.py`
**Fix:** `corridor_id = f"COR-{re.sub(r'[^A-Za-z0-9_-]', '_', str(target_id))}"` — non-alphanumeric characters replaced with `_`.

## Test Results
```
33 passed in 0.57s
```
All pre-existing tests passed without modification. The heading_deg fix did not break any tests because no test asserted a specific compass bearing value for auto-detected corridors.
