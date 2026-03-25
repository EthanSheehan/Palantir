# Add Shapely (Backend) and turf.js (Frontend) for Geometry (W1-020)

## Summary
Replace hand-rolled geometry calculations with battle-tested libraries: Shapely for Python zone math in battlespace_assessment.py, turf.js for frontend geospatial trig in Cesium hooks.

## Files to Modify
- `requirements.txt` — Add `shapely>=2.0`
- `src/python/battlespace_assessment.py` — Replace inline polygon/distance calculations with Shapely
- `src/frontend-react/package.json` — Add `@turf/turf`
- `src/frontend-react/src/cesium/` — Replace inline trig in hooks with turf.js equivalents

## Files to Create
- None (modifications to existing files)

## Test Plan (TDD — write these FIRST)
1. `test_zone_polygon_containment_shapely` — Point-in-polygon using Shapely matches current behavior
2. `test_zone_area_calculation_shapely` — Zone area calculation matches current implementation
3. `test_threat_cluster_geometry_shapely` — Cluster centroid/radius using Shapely
4. `test_existing_assessment_tests_pass` — All 21 battlespace assessment tests still pass

## Implementation Steps
1. Add `shapely>=2.0` to `requirements.txt`
2. In `battlespace_assessment.py`:
   - Replace manual point-in-polygon with `shapely.geometry.Point.within(Polygon(...))`
   - Replace manual distance calculations with `shapely.ops.nearest_points()` where applicable
   - Replace manual area calculations with `Polygon.area`
3. Add `@turf/turf` to frontend: `cd src/frontend-react && npm install @turf/turf`
4. In Cesium hooks, replace inline haversine/bearing calculations with `turf.distance()`, `turf.bearing()`, `turf.destination()`

## Verification
- [ ] All 21 battlespace assessment tests pass
- [ ] Shapely used for polygon operations (no inline polygon math)
- [ ] turf.js used in at least 3 Cesium hooks
- [ ] Frontend builds without errors

## Rollback
- Revert battlespace_assessment.py; remove shapely from requirements; revert frontend hooks; remove @turf/turf
