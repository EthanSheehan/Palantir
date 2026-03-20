---
phase: 09-map-modes-tactical-views
plan: 02
subsystem: cesium-layers
tags: [cesium, layers, typescript, groundprimitive, ellipsegeometry]

requires:
  - phase: 09-map-modes-tactical-views
    plan: 01
    provides: mapMode-store, layerVisibility-store

provides:
  - useCoverageLayer hook — sensor footprint ellipses per UAV colored by sensor type
  - useThreatLayer hook — SAM/MANPADS threat range circles from target data
  - useFusionLayer hook — confidence-colored ellipses at target positions
  - useSwarmLayer hook — dashed polylines from UAVs to primary targets
  - useTerrainLayer hook — terrain exaggeration toggle and LOS lines

affects: [09-03-integration]

tech-stack:
  added: []
  patterns:
    - "GroundPrimitive with show toggle for polygon layers (coverage, threat, fusion)"
    - "viewer.entities for line layers (swarm, terrain)"
    - "Rebuild primitive only when data count changes — not every 10Hz tick"
    - "Cleanup resets terrain exaggeration to 1.0 to prevent bleed"

key-files:
  created:
    - src/frontend-react/src/cesium/layers/useCoverageLayer.ts
    - src/frontend-react/src/cesium/layers/useThreatLayer.ts
    - src/frontend-react/src/cesium/layers/useFusionLayer.ts
    - src/frontend-react/src/cesium/layers/useSwarmLayer.ts
    - src/frontend-react/src/cesium/layers/useTerrainLayer.ts

key-decisions:
  - "GroundPrimitive for ellipse layers (coverage/threat/fusion) — GPU-efficient fill on terrain"
  - "Rebuild primitive only when UAV/target count changes, not every tick"
  - "Swarm and Terrain use viewer.entities since polyline count is small (no GPU batch needed)"
  - "useTerrainLayer guards terrainExaggeration with 'in' operator for forward compat"
  - "confidenceColor helper maps 4 bands: red(0-0.3), orange(0.3-0.6), yellow(0.6-0.9), green(0.9-1.0)"

requirements-completed: [FR-8]

duration: 260s
completed: 2026-03-20
---

# Phase 09 Plan 02: Cesium Layer Hooks Summary

**5 Cesium layer hooks reading layerVisibility from Zustand — coverage/threat/fusion use GroundPrimitive, swarm/terrain use viewer.entities**

## Performance

- **Duration:** ~260s
- **Started:** 2026-03-20T14:44:15Z
- **Completed:** 2026-03-20T15:08:35Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments

- Created `useCoverageLayer` — GroundPrimitive EllipseGeometry per UAV, colored by first sensor type (EO_IR=cyan, SAR=yellow, SIGINT=purple), rebuilds only when UAV count changes
- Created `useThreatLayer` — GroundPrimitive EllipseGeometry for SAM/MANPADS targets with threat_range_km radius, rebuilds when detected threat count changes
- Created `useFusionLayer` — GroundPrimitive EllipseGeometry (2km fixed radius) at target positions colored by fused_confidence (4-band: red/orange/yellow/green)
- Created `useSwarmLayer` — viewer.entities dashed polylines from UAV positions to primary tracked targets for FOLLOW/PAINT/INTERCEPT/SUPPORT modes
- Created `useTerrainLayer` — sets terrainExaggeration=2.0 when visible, draws viewer.entities LOS lines from UAVs to targets, resets to 1.0 on hide/cleanup

## Task Commits

1. **Task 1: useCoverageLayer + useThreatLayer** — `5930e99` (feat)
2. **Task 2: useFusionLayer + useSwarmLayer + useTerrainLayer** — `249ed98` (feat)

## Files Created

- `src/frontend-react/src/cesium/layers/useCoverageLayer.ts` — EO_IR/SAR/SIGINT colored sensor footprints
- `src/frontend-react/src/cesium/layers/useThreatLayer.ts` — SAM/MANPADS threat rings
- `src/frontend-react/src/cesium/layers/useFusionLayer.ts` — confidence heatmap ellipses
- `src/frontend-react/src/cesium/layers/useSwarmLayer.ts` — dashed assignment polylines
- `src/frontend-react/src/cesium/layers/useTerrainLayer.ts` — terrain exaggeration + LOS lines

## Decisions Made

- GroundPrimitive chosen for polygon layers (coverage/threat/fusion) — terrain-clipping GPU pass, better than Entity ellipses at scale
- Rebuild on count-change only: avoids GroundPrimitive rebuild every 10Hz tick when data is stable
- `viewer.entities` for swarm/terrain lines since line count is O(UAVs) — no GPU batching needed
- `terrainExaggeration` reset to 1.0 in both the "hide" branch and cleanup function — prevents bleed across mode switches

## Deviations from Plan

None — plan executed exactly as written. All 5 hooks follow the useCesiumZones lifecycle pattern precisely.

## Self-Check: PASSED

- useCoverageLayer.ts: FOUND
- useThreatLayer.ts: FOUND
- useFusionLayer.ts: FOUND
- useSwarmLayer.ts: FOUND
- useTerrainLayer.ts: FOUND
- TypeScript compiles clean: CONFIRMED
- All hooks check layerVisibility from store: CONFIRMED
- Coverage/Threat/Fusion use GroundPrimitive with show toggle: CONFIRMED
- Swarm/Terrain use viewer.entities: CONFIRMED
- Terrain cleanup resets exaggeration to 1.0: CONFIRMED

---
*Phase: 09-map-modes-tactical-views*
*Completed: 2026-03-20*
