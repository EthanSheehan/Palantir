# Fix RTB Mode with Real Return Logic (W1-022)

## Summary
Implement actual return-to-base navigation for RTB mode. Currently drones "drift slowly" with no destination. Add home_position from theater config and navigate using `_turn_toward()`.

## Files to Modify
- `src/python/sim_engine.py` — Add `home_position` to UAV initialization; implement real RTB navigation in the RTB mode handler using `_turn_toward()`
- `theaters/*.yaml` — Add `base_location` coordinates (if not already present)

## Files to Create
- `src/python/tests/test_rtb_navigation.py` — RTB navigation tests

## Test Plan (TDD — write these FIRST)
1. `test_rtb_navigates_toward_home` — Drone in RTB mode moves toward home_position
2. `test_rtb_uses_turn_toward` — Heading changes via `_turn_toward()` (smooth arcs, not teleporting)
3. `test_rtb_transitions_to_idle_on_arrival` — When within threshold of home, mode changes to IDLE
4. `test_rtb_home_from_theater_config` — home_position sourced from theater config or spawn position

## Implementation Steps
1. In UAV initialization (sim_engine.py), store `home_position = (spawn_lat, spawn_lon)` or from theater YAML `base_location`
2. In the RTB mode handler:
   ```python
   if drone.mode == "RTB":
       home_lat, home_lon = drone.home_position
       dist = haversine(drone.lat, drone.lon, home_lat, home_lon)
       if dist < ARRIVAL_THRESHOLD_KM:
           drone.mode = "IDLE"
       else:
           target_heading = bearing(drone.lat, drone.lon, home_lat, home_lon)
           drone.heading = _turn_toward(drone.heading, target_heading, dt)
           # Move forward at cruise speed
   ```
3. Check theater YAML files for existing `base_location` field; add if missing
4. Ensure `_turn_toward()` is used for smooth heading changes

## Verification
- [ ] Drones in RTB mode navigate to home and transition to IDLE
- [ ] No "drift slowly" placeholder remains
- [ ] All existing tests pass
- [ ] Demo shows RTB drones returning to base visually on the map

## Rollback
- Revert RTB handler to original drift logic
