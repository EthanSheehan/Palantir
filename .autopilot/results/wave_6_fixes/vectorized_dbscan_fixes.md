# Wave 6 MEDIUM Fixes: vectorized_detection + dbscan_clustering

**Status: ALL PASS — 63/63 tests green**

---

## vectorized_detection.py

### M3: Private import fixed
- Renamed `_FALLBACK_RCS_M2` → `FALLBACK_RCS_M2` (public) in `sensor_model.py`
- Added backwards-compatible alias `_FALLBACK_RCS_M2 = FALLBACK_RCS_M2` in sensor_model.py
- Updated import in vectorized_detection.py to use `FALLBACK_RCS_M2`

### M-SEC1: sensor_type validation added
- Added guard at top of `vectorized_detection_probability()` before the dict lookup:
  ```python
  if sensor_type not in SENSOR_CONFIGS:
      raise ValueError(f"Unknown sensor_type {sensor_type!r}. Valid types: {list(SENSOR_CONFIGS)}")
  ```

### M-SEC2: NaN/inf input guards added
- In `detect_all()`, after constructing `uav_pos`, `tgt_pos`, and `rcs` arrays:
  ```python
  if not np.all(np.isfinite(uav_pos)): raise ValueError(...)
  if not np.all(np.isfinite(tgt_pos)): raise ValueError(...)
  if not np.all(np.isfinite(rcs)):     raise ValueError(...)
  ```

---

## dbscan_clustering.py

### M1: Intentional mutation documented
- Added docstring note to `_expand_cluster()` explaining that `labels` mutation
  is intentional — the list is owned by `run_dbscan` and mutation is part of
  the standard DBSCAN algorithm contract.

### M6: O(N²) complexity documented
- Added docstring note to `match_clusters()` explaining O(N²) complexity and
  why it is acceptable (cluster counts bounded by MAX_TARGETS, typically < 20).

### M-SEC1: MAX_TARGETS cap added
- Added `MAX_TARGETS = 500` module-level constant
- `run_dbscan()` truncates input to `targets[:MAX_TARGETS]` before processing

### M-SEC2: Malformed target validation added
- `run_dbscan()` wraps lat/lon extraction in try/except, skipping any target
  dict that is missing keys or has non-numeric lat/lon values

---

## Test Results

```
63 passed in 1.44s
```

Files modified:
- `src/python/sensor_model.py` — FALLBACK_RCS_M2 made public
- `src/python/vectorized_detection.py` — public import, sensor_type validation, NaN/inf guards
- `src/python/dbscan_clustering.py` — MAX_TARGETS cap, malformed target skip, complexity comments
