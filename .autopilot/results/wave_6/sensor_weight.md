# W6-020: Dynamic Sensor Weighting — Results

## Status: COMPLETE

## Files Created
- `src/python/sensor_weighting.py` — 180 lines
- `src/python/tests/test_sensor_weighting.py` — 30 tests (all passing)

## Implementation Summary

### SensorFitness dataclass (frozen)
Fields: `sensor_type`, `weather_weight`, `time_weight`, `target_weight`, `combined_weight`

### compute_sensor_fitness(sensor_type, weather, time_of_day, target_type) -> SensorFitness
Per-sensor fitness functions:

| Sensor | Weather | Time of Day | Target |
|--------|---------|-------------|--------|
| EO/IR  | Degrades in RAIN/STORM (up to 85% penalty in full storm) | Cosine curve — peak noon, floor 0.35 at night (IR compensation) | Reduced 0.55× for MANPADS/UAV |
| SAR    | Near-immune (max 15% penalty at full storm intensity) | Neutral (0.9) | 0.85 for large metal, 0.45 for small targets |
| SIGINT | Unaffected (0.95) | Neutral (0.9) | 1.0 for C2_NODE/RADAR, 0.35 for small/silent |

Combined weight = geometric mean of three axes, clamped [0, 1].

### weight_fusion_contributions(contributions, weather, time_of_day=12.0) -> list
Returns new `SensorContribution` instances (immutable — `dataclasses.replace`) with confidence scaled by `combined_weight`. Original list untouched.

### recommend_sensor_type(weather, target_type, time_of_day=12.0) -> str
Evaluates all three sensors, returns highest `combined_weight`.

**Key routing decisions:**
- Storm + any target → SAR wins (weather_weight stays ~0.85, EO/IR collapses to ~0.09)
- Clear + C2_NODE/RADAR → SIGINT wins (target_weight=1.0 edges out EO/IR)
- Clear + daytime + most targets → EO/IR wins (max fitness in ideal conditions)

## Test Results
- New tests: 30 / 30 passing
- Full suite: 1787 passed, 1 pre-existing failure (test_enemy_uavs::test_jamming_enemy_detected_by_sigint — existed before this feature)

## Acceptance Criteria Checklist
- [x] Per-sensor `fitness_function(weather, time_of_day, target_type)` returning weight multiplier
- [x] Fusion weights recalculated each tick based on environment (via `weight_fusion_contributions`)
- [x] ISR priority prefers SAR drones when weather degrades EO/IR (`recommend_sensor_type` returns SAR in storm)
