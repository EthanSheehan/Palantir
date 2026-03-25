# Fix SampledPositionProperty Frontend Memory Leak (W1-006)

## Summary
Add rolling window pruner for Cesium SampledPositionProperty samples (cap at 600 = 60 seconds at 10Hz) and optimize tether geometry updates to prevent demo freezing after 10 minutes.

## Files to Modify
- `src/frontend-react/src/cesium/` — Find the hook(s) that add SampledPositionProperty samples for drones; add pruning logic
- `src/frontend-react/src/hooks/` — Check for drone entity hooks that accumulate position samples

## Files to Create
- None (inline fix in existing Cesium hooks)

## Test Plan (TDD — write these FIRST)
1. `test_position_samples_capped_at_600` — After adding 1000 samples, only 600 remain
2. `test_tether_updates_at_10hz_not_60fps` — Tether geometry uses CallbackProperty with throttle or pre-computed update

## Implementation Steps
1. Find where `SampledPositionProperty.addSample()` is called for drone entities (likely in `useDroneEntities` or similar hook)
2. After each `addSample()`, check `property._property._times.length` (or equivalent); if > 600, remove oldest samples
3. For tether lines: replace 60fps CallbackProperty with a pre-computed geometry that updates when drone positions change (10Hz from WebSocket)
4. Test by running demo for 30+ minutes and monitoring browser memory

## Verification
- [ ] Browser DevTools shows stable memory after 30 minutes
- [ ] Cesium globe remains responsive at 60fps after extended demo
- [ ] Drone trails still visible for last 60 seconds

## Rollback
- Revert the Cesium hook changes; remove pruning logic
