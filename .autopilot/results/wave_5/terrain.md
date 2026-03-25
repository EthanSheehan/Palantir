# W5-005: Terrain Analysis Module — PASS

## Status
COMPLETE — all tests green

## Deliverables

### New file: `src/python/terrain_model.py`
- `TerrainFeature` — frozen dataclass: center_lat, center_lon, radius_km, peak_elevation_m (conical elevation model)
- `TerrainModel` — frozen dataclass holding a tuple of TerrainFeature
- `has_line_of_sight(terrain, obs_lat, obs_lon, obs_alt, tgt_lat, tgt_lon, tgt_alt)` → bool
  - Ray-marches 50 samples along the path, checks terrain elevation at each sample
  - None or empty TerrainModel → always True (backwards compatible)
- `compute_dead_zones(terrain, obs_lat, obs_lon, obs_alt, grid_resolution)` → list[tuple[float,float]]
  - Sweeps bounding box of terrain features, returns blocked (lat,lon) grid points
- `load_terrain_from_config(config_dict)` → TerrainModel
  - Reads optional `terrain_features` list from theater YAML dict

### Modified: `src/python/sensor_model.py`
- Added optional `terrain_model` parameter to `evaluate_detection()`
- If terrain_model provided and LOS blocked → DetectionResult with pd=0.0, detected=False
- Backwards compatible: existing callers without terrain_model work unchanged

### New test file: `src/python/tests/test_terrain_model.py`
- 30 tests covering:
  - Immutability (frozen dataclasses)
  - Flat terrain always has LOS
  - Mountain blocks LOS at ground level
  - High altitude clears LOS over mountain
  - Grazing angle edge case
  - Dead zone computation (list, tuples, non-empty, empty, fewer when high)
  - Config loading (no features, with features, multiple features, empty)
  - Default/None terrain model always has LOS
  - Integration: blocked LOS → pd=0, clear LOS → nonzero pd, backwards compat

## Test Results
- Terrain tests: 30/30 passed
- Sensor model tests: 36/36 passed (no regressions)
- Full suite terrain+sensor: 66/66 passed

## Theater YAML Extension
Theater configs can now include optional `terrain_features`:
```yaml
terrain_features:
  - center_lat: 45.5
    center_lon: 25.5
    radius_km: 20.0
    peak_elevation_m: 2500.0
```
Existing theaters without this key continue to work (empty TerrainModel, LOS always True).
