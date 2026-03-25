# W3-004: Swarm Coordinator Upgrade — Hungarian Algorithm

## Status: COMPLETE

## Changes Made

### `src/python/swarm_coordinator.py`
- Replaced greedy O(T*gaps*U) assignment with `scipy.optimize.linear_sum_assignment` for optimal UAV-to-target matching
- Added `_build_cost_matrix(uavs, task_list)` helper: cost = distance / priority_score, infeasible entries = 1e18
- Added `_hungarian_assign(available, task_list, idle_count)` to run the algorithm and convert results to TaskingOrders
- Added `_detect_drone_loss(uavs)`: detects when assigned UAVs disappear from the UAV list, removes them from active tasks, marks targets for priority promotion (+50% boost via `_DRONE_LOSS_PRIORITY_BOOST = 1.5`)
- Added `_detect_byzantine(uavs)`: tracks UAV positions between ticks, flags any UAV whose position changes >50km (≈180,000 km/h at 10Hz) as anomalous and excludes from assignment
- Added `_last_positions`, `_byzantine_flagged`, `_promoted_targets` state tracking
- New constants: `_BYZANTINE_THRESHOLD_KM = 50.0`, `_DRONE_LOSS_PRIORITY_BOOST = 1.5`
- New imports: `numpy`, `scipy.optimize.linear_sum_assignment`

### Backward Compatibility Preserved
- Same `SwarmTask` frozen dataclass output format
- Same public API: `evaluate_and_assign(targets, uavs, ...)` returns `list[TaskingOrder]`
- Same priority scoring formula: `threat_weight * (1 - fused_confidence)`
- Same 120s task expiry
- Same idle-count guard
- Same auto-release on resolved target states

### `src/python/tests/test_hungarian_swarm.py` — 11 new tests
1. `test_optimal_assignment_3x3` — 3 UAVs, 3 targets, verifies optimal (not greedy) matching
2. `test_more_uavs_than_targets` — 5 UAVs, 2 targets, only 2 assigned
3. `test_more_targets_than_uavs` — 1 UAV, 3 targets, highest priority gets it
4. `test_empty_uav_list` — returns empty
5. `test_empty_target_list` — returns empty
6. `test_single_uav_single_target` — basic assignment
7. `test_priority_scoring_unchanged` — verifies formula still works
8. `test_task_expiry_still_works` — 120s expiry preserved
9. `test_lost_uav_task_reprioritized` — drone loss removes UAV from active task
10. `test_teleporting_uav_flagged` — Byzantine detection skips teleporting UAV
11. `test_normal_movement_not_flagged` — normal movement not affected

## Test Results
- 11/11 new tests: PASS
- 13/13 existing swarm tests: PASS
- Full suite: 1 pre-existing failure (test_enemy_uavs), 5 pre-existing errors (test_mission_store) — none related to this change
