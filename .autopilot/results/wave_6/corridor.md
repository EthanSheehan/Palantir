# W6-028: Corridor Detection Upgrade — Results

## Status: COMPLETE

## Files Created

- `src/python/corridor_detection.py` — new module (177 lines)
- `src/python/tests/test_corridor_detection.py` — 33 tests (all passing)

## Acceptance Criteria

| Criteria | Status |
|---|---|
| Douglas-Peucker path simplification | DONE — `douglas_peucker(points, epsilon)` |
| Directional consistency check (not just displacement) | DONE — `compute_heading_consistency(points)` returns 0.0–1.0 using circular mean heading variance |
| Corridor attribution (targets, time range, speed) | DONE — `Corridor` dataclass has `target_ids`, `time_start`, `time_end`, `speed_avg` |

## API

### `Corridor` (frozen dataclass)
- `corridor_id: str`
- `start_point: Tuple[float, float]`
- `end_point: Tuple[float, float]`
- `waypoints: Tuple[Tuple[float, float], ...]`
- `target_ids: Tuple[str, ...]`
- `heading_deg: float`
- `speed_avg: float` (km/h)
- `time_start: Optional[float]`
- `time_end: Optional[float]`
- `confidence: float` (0.0–1.0, equals heading consistency)

### `douglas_peucker(points, epsilon) -> list`
Ramer-Douglas-Peucker simplification. Endpoints always preserved. Pure recursive implementation using perpendicular distance.

### `compute_heading_consistency(points) -> float`
Circular mean of segment headings; mean absolute angular deviation normalised to [0, 1]. Patrol loops score <0.5, straight paths score >0.95.

### `detect_corridors(target_histories, min_points=5, epsilon_km=0.5, min_consistency=0.6) -> list[Corridor]`
Full pipeline: extract points → simplify → check consistency → emit Corridor.

### `attribute_corridor(corridor, all_targets) -> Corridor`
Filters `target_ids` to only those present in `all_targets`. Returns new frozen Corridor.

## Test Results

```
33 passed in 0.33s
```

Full suite (excluding pre-existing broken `test_uav_kinematics.py`):
```
1 failed (pre-existing: test_jamming_enemy_detected_by_sigint), 1746 passed
```

No regressions introduced.

## Key Design Decisions

- `math` stdlib only — no numpy/scipy (as required)
- All functions pure — no mutation of inputs
- Epsilon converted from km to degrees using 111 km/deg approximation
- Heading consistency uses circular mean to handle 0°/360° wraparound correctly
- Patrol loop detection: circular paths produce high heading variance → consistency near 0, filtered out by `min_consistency`
