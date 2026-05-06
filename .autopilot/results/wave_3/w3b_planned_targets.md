---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# Wave 3B — Planned Targets / Aimpoints

## Status: COMPLETE

## What Was Built

### Backend

**`src/python/target_store.py`** (new file)
- `Aimpoint` and `PlannedTarget` frozen dataclasses
- `TargetStore` class with SQLite persistence (`planned_targets.db`)
- Tables: `planned_targets` and `aimpoints` (FK with CASCADE delete)
- Methods: `add_target`, `get_all`, `delete_target`, `to_dict_list`
- Parameterized SQL — no injection risk

**`src/python/api_main.py`** (modified)
- Import: `from target_store import Aimpoint, PlannedTarget, TargetStore`
- `import uuid` added to stdlib imports
- `target_store = TargetStore()` initialized at module level
- Three new REST endpoints:
  - `GET /api/planned-targets` — returns all targets
  - `POST /api/planned-targets` — creates target with optional aimpoints; validates name/lat/lon required
  - `DELETE /api/planned-targets/{target_id}` — deletes target (404 if not found)
- `target_store` passed to `simulation_loop()`

**`src/python/simulation_loop.py`** (modified)
- `target_store: TargetStore | None = None` optional param added to `simulation_loop()`
- `SimulationLoopState` gets `last_planned_targets_time` and `cached_planned_targets` fields
- Refreshes planned_targets cache every 5 seconds and includes in WS state broadcast as `planned_targets`

### Frontend

**`src/frontend-react/src/store/SimulationStore.ts`** (modified)
- `plannedTargets: any[]` added to `SimState` interface
- `plannedTargets: []` initial state
- `planned_targets?: any[]` added to `setSimData` data param
- `plannedTargets: data.planned_targets || []` in `set()` call

**`src/frontend-react/src/panels/enemies/PlannedTargetsCard.tsx`** (new file)
- Displays planned targets list with priority color-coding (P1=danger, P2=warning, P3=primary, P4=success)
- Shows aimpoints with coordinates under each target
- Empty state message when no planned targets

**`src/frontend-react/src/panels/enemies/EnemiesTab.tsx`** (modified)
- Imports `PlannedTargetsCard`
- Reads `plannedTargets` from store
- Renders `<PlannedTargetsCard targets={plannedTargets} />` at bottom of entities list

## Test Results

- 1811 passed, 0 failed (full test suite)
- Manual verification of `target_store.py` logic: add/get/delete/cascade all correct
