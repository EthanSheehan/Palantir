---
phase: 00-foundation-react-migration
plan: 03
status: complete
---

## Summary

Created four core Cesium entity hooks ported from the vanilla JS frontend.

## Key Files

- `src/frontend-react/src/cesium/useCesiumDrones.ts` — Drone entities with SampledPositionProperty, Hermite interpolation, 3D model/billboard/point LOD, tether polylines
- `src/frontend-react/src/cesium/useCesiumTargets.ts` — Target entities with type-specific SVG icons, threat rings for SAM/MANPADS
- `src/frontend-react/src/cesium/useCesiumZones.ts` — Zone grid GroundPrimitive with create-once/update-attributes pattern, imbalance coloring
- `src/frontend-react/src/cesium/useCesiumFlowLines.ts` — Cyan glow polylines for drone-target flow assignments
- `src/frontend-react/src/cesium/CesiumContainer.tsx` — Updated to wire all four hooks

## Commits

- `4330910` feat(00-03): Cesium entity hooks for drones, targets, zones, flow lines
