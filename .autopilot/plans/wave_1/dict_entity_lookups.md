# Replace O(N) Entity Lookups with Dict (W1-009)

## Summary
Replace `_find_uav()`, `_find_target()`, `_find_enemy_uav()` O(N) linear scans with O(1) dict lookups by storing entities as dicts keyed by ID.

## Files to Modify
- `src/python/sim_engine.py` — Change `self.drones`, `self.targets`, `self.enemy_uavs` from lists to dicts; update all iteration to use `.values()`; replace `_find_*()` methods with direct dict access
- `src/python/api_main.py` — Update any code that assumes list-based entity storage

## Files to Create
- `src/python/tests/test_dict_lookups.py` — Tests for O(1) lookup behavior

## Test Plan (TDD — write these FIRST)
1. `test_find_uav_by_id_returns_correct_drone` — Dict lookup returns correct drone
2. `test_find_uav_missing_id_returns_none` — Missing ID returns None (not crash)
3. `test_find_target_by_id_returns_correct_target` — Dict lookup for targets
4. `test_find_enemy_uav_by_id` — Dict lookup for enemy UAVs
5. `test_all_iteration_uses_values` — Existing iteration patterns still work with `.values()`

## Implementation Steps
1. In `sim_engine.py`, change `self.drones = []` to `self.drones = {}` (keyed by drone.id)
2. Change `self.targets = []` to `self.targets = {}` (keyed by target.id)
3. Change `self.enemy_uavs = []` to `self.enemy_uavs = {}` (keyed by enemy.id)
4. Replace `_find_uav(id)` with `self.drones.get(id)`
5. Replace `_find_target(id)` with `self.targets.get(id)`
6. Replace `_find_enemy_uav(id)` with `self.enemy_uavs.get(id)`
7. Update all `for drone in self.drones:` to `for drone in self.drones.values():`
8. Update `get_state()` serialization to use `.values()`
9. Update `api_main.py` code that accesses entities by list index or linear scan

## Verification
- [ ] All 475 existing tests pass
- [ ] `_find_uav`, `_find_target`, `_find_enemy_uav` methods removed or simplified to `dict.get()`
- [ ] No O(N) scans remain for entity lookup
- [ ] Demo runs correctly with dict-based storage

## Rollback
- Revert `sim_engine.py` and `api_main.py` to list-based storage
