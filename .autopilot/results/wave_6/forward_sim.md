# W6-001: Forward Simulation Branches — Results

## Status: COMPLETE

## Files Created
- `src/python/forward_sim.py` — implementation (130 lines)
- `src/python/tests/test_forward_sim.py` — 21 tests (TDD, written first)

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `clone_simulation(model)` using deepcopy | DONE |
| `project_forward(model, ticks)` function | DONE |
| `asyncio.to_thread()` per COA candidate | DONE |
| Select max-score projected COA (sorted desc) | DONE |
| Predicted outcome surfaced in COA rationale (`projected_state_summary`) | DONE |

## API

```python
from forward_sim import clone_simulation, score_state, project_forward, evaluate_coas

# Clone state (deep copy, handles circular grid neighbor refs)
cloned = clone_simulation(model)

# Score a state snapshot
score = score_state(model)  # float >= 0

# Project one COA forward (blocking, returns float score)
score = project_forward(model, ticks=50)

# Evaluate multiple COAs in parallel (async)
ranked_coas = await evaluate_coas(model, coas, ticks=50)
# Each coa now has: projected_score (float) + projected_state_summary (dict)
# projected_state_summary keys: verified_targets, active_threats, drone_health
```

## Scoring Function

`score_state` weights:
- VERIFIED target: +3.0
- CLASSIFIED/TRACKED/LOCKED/NOMINATED target: +1.8
- DETECTED target: +0.5
- DESTROYED/ESCAPED target: -5.0
- UAV fuel health: +0.2 × (fuel_hours / 6.0) per UAV

## Technical Notes

- `clone_simulation` temporarily raises `sys.setrecursionlimit` to 10000 to handle `RomaniaMacroGrid.GridZone.neighbors` circular list references; restores original limit in a `finally` block.
- `evaluate_coas` spawns one `asyncio.to_thread` coroutine per COA — runs projection and summary extraction in parallel. Original model is never mutated.
- All projections are pure side-effect-free against the caller's model.

## Test Results

```
21 passed in 2.02s
```

Full suite: 1518 passed, 1 pre-existing failure (test_jamming_enemy_detected_by_sigint — unrelated to this feature)
