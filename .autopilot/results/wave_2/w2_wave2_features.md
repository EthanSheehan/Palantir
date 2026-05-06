---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# Wave 2 Features — Build Results

## Status: COMPLETE

All 3 features built successfully.

---

## Feature 1: Multi-UAV Selection (Shift-Click Additive)

**Files modified:**
- `src/frontend-react/src/store/SimulationStore.ts`
- `src/frontend-react/src/cesium/useCesiumClickHandlers.ts`

**Changes:**
- Added `selectedDroneIds: number[]` to SimState interface and initial state (`[]`)
- Added `selectDroneAdditive(id)` action — toggles id in/out of `selectedDroneIds`, sets `selectedDroneId` to id
- Updated `selectDrone(id)` to also reset `selectedDroneIds` to `[id]` (or `[]` for null)
- In click handler: track `lastShiftState` via `keydown`/`keyup` listeners
- On UAV click with shift held: calls `selectDroneAdditive` instead of `selectDrone`
- Captured shift state at click time (`shiftAtClick`) before the 250ms timer fires to avoid race

---

## Feature 2: Workspace Mode Tabs (ISR/Plan)

**Files modified:**
- `src/frontend-react/src/store/types.ts`
- `src/frontend-react/src/store/SimulationStore.ts`
- `src/frontend-react/src/panels/Sidebar.tsx`
- `src/frontend-react/src/App.tsx`

**Changes:**
- Added `WorkspaceMode = 'isr' | 'plan'` type to `types.ts`
- Added `workspaceMode: WorkspaceMode` and `setWorkspaceMode` to store interface, initial state (`'isr'`), and implementation
- Sidebar: added ISR/PLAN `ButtonGroup` above the "System Dashboard" title; active button highlighted with `Intent.PRIMARY`
- App.tsx: `I`/`i` key toggles between `'isr'` and `'plan'` modes

---

## Feature 3: Layout Persistence (localStorage)

**Files modified:**
- `src/frontend-react/src/store/SimulationStore.ts`

**Changes:**
- Added `loadPersistedLayout()` — reads `grid_sentinel_layout` from localStorage, returns partial state
- Persists: `mapMode`, `camLayout`, `workspaceMode`, `gridVisState`
- On module load: applies persisted values via `useSimStore.setState(persisted)` if any exist
- Subscribes to store changes to write layout state to localStorage on every update
- All localStorage operations wrapped in try/catch to silently handle quota errors
