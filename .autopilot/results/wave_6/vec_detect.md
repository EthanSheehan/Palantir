# W6-007: Vectorize Detection Loop with NumPy

**Status:** COMPLETE
**Date:** 2026-03-25

## Files Created

- `src/python/vectorized_detection.py` — vectorized detection module (186 lines)
- `src/python/tests/test_vectorized_detection.py` — 30 TDD tests (all pass)

## Implementation Summary

### API

| Function | Signature | Description |
|---|---|---|
| `positions_to_array` | `(entities: list) -> np.ndarray (N,2)` | Extract lat/lon as float64 array |
| `pairwise_distances_km` | `(uav_pos: ndarray, target_pos: ndarray) -> ndarray (M,N)` | MxN distance matrix, km, flat-earth |
| `vectorized_detection_probability` | `(distances, rcs, weather_factor, sensor_type) -> ndarray (M,N)` | Element-wise Pd, mirrors compute_pd() |
| `detect_all` | `(uavs, targets, weather_factor, sensor_type, threshold) -> list[tuple]` | Returns (uav_id, target_id, pd) above threshold |
| `benchmark_scalar_vs_vectorized` | `(n_uavs, n_targets) -> dict` | Timing comparison scalar vs numpy |

### Key Design Decisions

- **Flat-earth equirectangular** distance (same as `sensor_model.deg_to_meters`) — accurate <1% within 200 km
- **Broadcast pattern**: `uav_pos[:, np.newaxis]` × `target_pos[np.newaxis, :]` gives (M,N) without loops
- **Immutable**: all functions return new arrays, no mutation of input lists
- **Weather**: maps `weather_factor` → `cloud_cover` in same formula as `compute_pd()`
- **Stable sigmoid**: clips x to [-500, 500] to prevent exp overflow
- **numpy** already in requirements.txt (>=1.24.0) — no changes needed

## Test Results

```
30 passed in 0.27s
```

Tests cover:
- `positions_to_array`: empty, single, multi, dtype, immutability
- `pairwise_distances_km`: shape (M,N), known distances, scalar equivalence, non-negative, dtype
- `vectorized_detection_probability`: shape, bounds [0,1], monotonicity (closer=higher Pd), weather degradation, SAR vs EO_IR range, exact scalar match, dtype
- `detect_all`: return types, tuple structure, close/far threshold behavior, custom threshold, immutability, unknown target type
- Bulk equivalence: 5×20 grid vs scalar compute_pd, abs tolerance 1e-4

## Benchmark Results (n_uavs=10)

| Targets | Scalar | Vectorized | Speedup |
|---------|--------|------------|---------|
| 100 | 1.9 ms | 0.2 ms | **7.9x** |
| 500 | 10.3 ms | 0.5 ms | **22.0x** |
| 1000 | 24.1 ms | 1.8 ms | **13.1x** |

Meets acceptance criteria (10-50x speedup at large scale). The 500-target case peaks at 22x.

## Full Suite Impact

1519 passed (up from 1371 pre-wave-6), 0 new failures.
Pre-existing flaky test `test_enemy_uavs.py::TestJammingDetection::test_jamming_enemy_detected_by_sigint` is unrelated to this feature.
