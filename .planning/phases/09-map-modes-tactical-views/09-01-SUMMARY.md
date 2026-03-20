---
phase: 09-map-modes-tactical-views
plan: 01
subsystem: ui
tags: [react, zustand, blueprintjs, typescript, cesium]

requires:
  - phase: 08-adaptive-isr
    provides: ISRQueue, CoverageModeToggle, ISR types and store fields

provides:
  - MapMode union type (OPERATIONAL/COVERAGE/THREAT/FUSION/SWARM/TERRAIN) exported from types.ts
  - MAP_MODE_DEFAULTS record mapping each mode to 9 layer visibility defaults
  - Zustand store extended with mapMode, layerVisibility, setMapMode, toggleLayer
  - MapModeBar overlay — Blueprint ButtonGroup top-right of globe with keyboard shortcuts 1-6
  - LayerPanel overlay — 9 Blueprint Checkbox toggles below MapModeBar

affects: [09-02-layer-hooks, 09-03-integration]

tech-stack:
  added: []
  patterns:
    - "Map mode atomically replaces layerVisibility from MAP_MODE_DEFAULTS on mode switch"
    - "Individual layer toggles override mode defaults via immutable spread update"
    - "Keyboard shortcuts guard against input element focus to prevent mode switching while typing"

key-files:
  created:
    - src/frontend-react/src/overlays/MapModeBar.tsx
    - src/frontend-react/src/overlays/LayerPanel.tsx
  modified:
    - src/frontend-react/src/store/types.ts
    - src/frontend-react/src/store/SimulationStore.ts

key-decisions:
  - "MAP_MODE_DEFAULTS defines canonical visibility for each mode; setMapMode does atomic replace via spread copy"
  - "layerVisibility is a flat Record<string, boolean> — layer hooks in Plan 02 read individual keys"
  - "MapModeBar positioned at top:16, right:16 to avoid collision with CameraControls at top-left"
  - "LayerPanel at top:56 sits directly below MapModeBar"

patterns-established:
  - "Overlay positioning: absolute over Cesium canvas, dark semi-transparent background, 1px border rgba(255,255,255,0.15)"

requirements-completed: [FR-8]

duration: 3min
completed: 2026-03-20
---

# Phase 09 Plan 01: Map Mode State System Summary

**Zustand map mode system with 6 modes, atomic layer visibility defaults, MapModeBar keyboard shortcuts 1-6, and LayerPanel checkboxes — foundation for Cesium layer hooks in Plan 02**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-20T14:57:12Z
- **Completed:** 2026-03-20T15:00:37Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `MapMode` union type and `MAP_MODE_DEFAULTS` record to `types.ts` — each of 6 modes maps to 9 layer visibility booleans
- Extended Zustand `SimState` with `mapMode`, `layerVisibility`, `setMapMode` (atomic mode+visibility reset), and `toggleLayer` (per-layer override)
- Created `MapModeBar` overlay — Blueprint ButtonGroup with active state highlighting, positioned top-right of Cesium globe, keyboard listener for keys 1-6 with input element guard
- Created `LayerPanel` overlay — 9 Blueprint Checkbox controls positioned below MapModeBar, reading and toggling `layerVisibility` from store

## Task Commits

1. **Task 1: MapMode type and store extension** - `b76a30d` (feat)
2. **Task 2: MapModeBar overlay** - `1a9e177` (feat, pre-existing from planner)
3. **Task 3: LayerPanel overlay** - `1a9e177` (feat, pre-existing from planner)

## Files Created/Modified

- `src/frontend-react/src/store/types.ts` - Added `MapMode` type and `MAP_MODE_DEFAULTS` constant
- `src/frontend-react/src/store/SimulationStore.ts` - Extended with mapMode, layerVisibility, setMapMode, toggleLayer
- `src/frontend-react/src/overlays/MapModeBar.tsx` - New: mode switcher ButtonGroup with keyboard shortcuts
- `src/frontend-react/src/overlays/LayerPanel.tsx` - New: per-layer toggle checkboxes

## Decisions Made

- `setMapMode` does an atomic replace of `layerVisibility` from `MAP_MODE_DEFAULTS[mode]` — ensures clean state on mode switch
- `layerVisibility` is a flat `Record<string, boolean>` rather than nested — layer hooks in Plan 02 read individual keys directly
- Overlay backdrop styling: `rgba(0,0,0,0.7)` background with `1px solid rgba(255,255,255,0.15)` border — consistent dark panel pattern

## Deviations from Plan

None - plan executed exactly as written. Overlay files were pre-staged by planner; store types were committed separately to satisfy type dependencies.

## Issues Encountered

None.

## Next Phase Readiness

- `layerVisibility` record is live in store, ready for Plan 02 Cesium layer hooks to consume
- `MapModeBar` and `LayerPanel` need to be mounted in `CesiumContainer` or App root in Plan 03 integration
- TypeScript compiles clean; no blockers for Plan 02

---
*Phase: 09-map-modes-tactical-views*
*Completed: 2026-03-20*
