# Phase 9: Map Modes & Tactical Views - Research

**Researched:** 2026-03-20
**Domain:** Cesium layer management, React/Zustand state, Blueprint UI, keyboard event handling
**Confidence:** HIGH

---

## Summary

Phase 9 adds 6 named map visualization modes (OPERATIONAL, COVERAGE, THREAT, FUSION, SWARM, TERRAIN) with keyboard shortcuts 1-6, individual layer toggles, and camera presets. The work is entirely frontend — no backend changes needed. All data required for the layers already flows in the WebSocket state payload: targets carry `threat_range_km`, `sensor_contributions`, `fused_confidence`, `tracked_by_uav_ids`; UAVs carry position, `sensors`, `tracked_target_ids`; zones carry `imbalance`. Assessment data from Phase 7 (ThreatCluster, CoverageGap) and swarm data from Phase 5 will also be in the payload.

The codebase has mature Cesium patterns: `useCesiumZones.ts` demonstrates the `GroundPrimitive` + `PerInstanceColorAppearance` approach for polygons; `useCesiumRangeRings.ts` demonstrates `viewer.entities.add()` with ellipses; `useCesiumFlowLines.ts` demonstrates polylines. All new layer hooks must follow the same lifecycle contract: subscribe to Zustand store inside a single `useEffect`, clean up by removing entities/primitives in the effect return. The mode bar and layer panel sit in the Cesium overlay layer (positioned absolute over the globe), consistent with `CameraControls.tsx`.

The only non-trivial implementation is TERRAIN mode. Cesium's world terrain is already loaded (`Cesium.Terrain.fromWorldTerrain()` in `useCesiumViewer.ts`) and `depthTestAgainstTerrain` is already `true`. LOS analysis requires a raycast from UAV position to target position using `viewer.scene.sampleHeight` or entity visibility — this is doable but compute-intensive; the approach must throttle to avoid blocking the render loop.

**Primary recommendation:** Implement map mode state in `SimulationStore.ts` (a `mapMode` string + `layerVisibility` record), wire each layer hook to read its visibility flag, and add a `MapModeBar` overlay component that sets mode and fires keyboard listeners. TERRAIN mode LOS analysis should be done lazily (on demand, not every tick).

---

## Standard Stack

### Core (all already in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cesium` | 1.114.0 | Layer rendering, primitives, terrain, camera | Already loaded, viewer initialized |
| `@blueprintjs/core` | 5.13.0 | ButtonGroup, Checkbox, Button for mode bar and layer panel | Project UI standard |
| `zustand` | 4.5.0 | `mapMode` + `layerVisibility` state | Locked at 4.5.0 (Decisions Log) |
| React 18 | 18.3.1 | Component layer, `useEffect`, `useRef` | Project standard |
| TypeScript | 5.5.0 | Typing for mode enum, visibility record | Project standard |

### No New Dependencies

This phase requires zero new npm packages. All Cesium primitives needed (GroundPrimitive, EllipseGeometry, PolylineGeometry, sampleHeight) are already in the `cesium` package at 1.114.0.

**Installation:** None required.

---

## Architecture Patterns

### Recommended Project Structure

```
src/frontend-react/src/
├── store/
│   └── SimulationStore.ts          MODIFY — add mapMode, layerVisibility, setMapMode, toggleLayer
├── cesium/
│   ├── CesiumContainer.tsx         MODIFY — mount new layer hooks
│   ├── layers/
│   │   ├── useCoverageLayer.ts     NEW (~150 lines)
│   │   ├── useThreatLayer.ts       NEW (~150 lines)
│   │   ├── useFusionLayer.ts       NEW (~120 lines)
│   │   ├── useTerrainLayer.ts      NEW (~150 lines)
│   │   └── useSwarmLayer.ts        NEW (~100 lines)
├── overlays/
│   ├── MapModeBar.tsx              NEW (~100 lines)
│   └── LayerPanel.tsx              NEW (~80 lines)
└── overlays/CameraPresets.tsx      NEW (~60 lines)  [or add to existing CameraControls]
```

Note: the phase description uses `src/frontend/src/` paths but the live frontend is `src/frontend-react/src/`. All new files go in `src/frontend-react/src/`.

### Pattern 1: Map Mode State in Zustand

**What:** Add `mapMode` (string enum) and `layerVisibility` (Record<string, boolean>) to `SimulationStore`. Modes configure default layer visibility when switched; individual layers can still be toggled independently.

**When to use:** All layer hooks read their visibility flag from this record; mode switching sets a batch of flags atomically.

```typescript
// Store extension — immutable update pattern
type MapMode = 'OPERATIONAL' | 'COVERAGE' | 'THREAT' | 'FUSION' | 'SWARM' | 'TERRAIN';

const MAP_MODE_DEFAULTS: Record<MapMode, Record<string, boolean>> = {
  OPERATIONAL: { drones: true, targets: true, zones: true, flows: true, coverage: false, threat: false, fusion: false, swarm: false, terrain: false },
  COVERAGE:    { drones: true, targets: false, zones: true, flows: false, coverage: true, threat: false, fusion: false, swarm: false, terrain: false },
  THREAT:      { drones: false, targets: true, zones: false, flows: false, coverage: false, threat: true, fusion: false, swarm: false, terrain: false },
  FUSION:      { drones: true, targets: true, zones: false, flows: false, coverage: false, threat: false, fusion: true, swarm: false, terrain: false },
  SWARM:       { drones: true, targets: true, zones: false, flows: true, coverage: false, threat: false, fusion: false, swarm: true, terrain: false },
  TERRAIN:     { drones: true, targets: true, zones: false, flows: false, coverage: false, threat: false, fusion: false, swarm: false, terrain: true },
};

setMapMode: (mode: MapMode) => set({ mapMode: mode, layerVisibility: { ...MAP_MODE_DEFAULTS[mode] } }),
toggleLayer: (layer: string) => set((state) => ({
  layerVisibility: { ...state.layerVisibility, [layer]: !state.layerVisibility[layer] }
})),
```

### Pattern 2: Cesium Layer Hook Structure

**What:** Each layer hook subscribes to Zustand store, checks its visibility flag, and removes/re-adds entities or shows/hides primitives. Follows the exact lifecycle of `useCesiumZones.ts`.

**When to use:** All five new layer hooks.

```typescript
// Pattern derived from useCesiumZones.ts and useCesiumRangeRings.ts
export function useCoverageLayer(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const primitiveRef = useRef<Cesium.Primitive | null>(null);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const visible = state.layerVisibility['coverage'] ?? false;

      if (!visible) {
        if (primitiveRef.current) {
          viewer.scene.primitives.remove(primitiveRef.current);
          primitiveRef.current = null;
        }
        return;
      }

      // Build or update coverage ellipses from state.uavs
      // ...
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed() && primitiveRef.current) {
        viewer.scene.primitives.remove(primitiveRef.current);
        primitiveRef.current = null;
      }
    };
  }, [viewerRef]);
}
```

### Pattern 3: Keyboard Shortcuts via useEffect

**What:** A single `useEffect` in `MapModeBar` (or a dedicated `useMapModeKeyboard` hook) attaches a `keydown` listener on `window`. Keys 1-6 map to modes. Must be careful not to fire when user is typing in an input.

**When to use:** MapModeBar component mount.

```typescript
// Source: standard browser DOM pattern
useEffect(() => {
  function onKeyDown(e: KeyboardEvent) {
    // Don't steal keys from input elements
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
    const modeMap: Record<string, MapMode> = {
      '1': 'OPERATIONAL', '2': 'COVERAGE', '3': 'THREAT',
      '4': 'FUSION', '5': 'SWARM', '6': 'TERRAIN',
    };
    const mode = modeMap[e.key];
    if (mode) setMapMode(mode);
  }
  window.addEventListener('keydown', onKeyDown);
  return () => window.removeEventListener('keydown', onKeyDown);
}, [setMapMode]);
```

### Pattern 4: Coverage Layer — Sensor Footprint Ellipses

**What:** For each UAV, draw a ground-level ellipse representing sensor coverage radius. Use `GroundPrimitive` + `EllipseGeometry` for performance (not `viewer.entities` ellipses, which are slower at 10Hz update rate).

**When to use:** COVERAGE mode.

Key parameters:
- Radius: `SENSOR_RANGE_KM * 1000` meters (already in `constants.ts` as `SENSOR_RANGE_KM = 15`)
- Color: semi-transparent, sensor-type tinted (EO_IR cyan, SAR yellow, SIGINT purple)
- Performance: rebuild primitive only when UAV count changes; update positions via `CallbackProperty` or full rebuild at 2Hz (not 10Hz)

### Pattern 5: Threat Layer — SAM Envelopes

**What:** Draw filled circles at each SAM/MANPADS target position with radius from `threat_range_km`. Already partially done in `THREAT_RING_TYPES` and `THREAT_RING_RADIUS` constants, but those are entity-based. The threat layer should use `GroundPrimitive` for better visual layering.

Phase 7 (BattlespaceAssessor) will also provide `ThreatCluster` data with `hull_points` for cluster polygons. The threat layer should render both: per-target rings AND per-cluster convex hulls.

**SAM envelope colors:**
- SAM: `rgba(255, 68, 68, 0.2)` fill, `rgba(255, 68, 68, 0.8)` outline
- MANPADS: `rgba(236, 72, 153, 0.2)` fill

### Pattern 6: Fusion Layer — Confidence Heatmap

**What:** Visualize sensor contribution coverage as colored ellipses per UAV at the target location, colored by fused confidence. No external heatmap library needed — use Cesium `GroundPrimitive` ellipses with alpha mapped to confidence value.

Data source: `state.targets[].sensor_contributions` (already in payload as of Phase 1).

Confidence color mapping:
- 0.0–0.3: red (low)
- 0.3–0.6: orange (medium)
- 0.6–0.9: yellow (high)
- 0.9–1.0: green (locked)

### Pattern 7: Swarm Layer — Formation Lines and Assignment Arrows

**What:** Draw dashed polylines from each UAV to its assigned target when in FOLLOW/PAINT/INTERCEPT/SUPPORT mode. Phase 5 will expose `swarm_tasks` in the payload. Assignment arrows use `viewer.entities` polylines (not primitives) since count is small.

Data source: `state.uavs[].tracked_target_ids` (already in payload, populated by swarm coordinator in Phase 5).

### Pattern 8: Terrain Layer — LOS Visualization

**What:** TERRAIN mode shows 3D terrain prominently and draws line-of-sight lines from UAVs to their tracked targets. True LOS analysis uses `viewer.scene.sampleHeight` along the geodesic, but this is expensive.

**Practical implementation:**
1. Toggle globe terrain exaggeration: `viewer.scene.globe.terrainExaggeration = 2.0` (TERRAIN mode) vs `1.0` (all other modes)
2. LOS lines: draw polylines from UAV position to target position; color green (clear) or red (occluded). LOS computed lazily on mode switch only, not every tick. Use `viewer.scene.clampToHeight` for approximate terrain intersection check.
3. Terrain masking indicators: entities at target positions with color coded by terrain visibility score.

**Key constraint:** `viewer.scene.sampleHeight` is async. Use `viewer.scene.sampleHeightMostDetailed` or simply skip full LOS — a visual line colored by approximate elevation delta is sufficient for this phase.

### Pattern 9: MapModeBar UI Layout

**What:** Positioned `absolute` in top-right of the Cesium globe area (consistent with `CameraControls` at top-left). Blueprint `ButtonGroup` with 6 buttons. Active mode highlighted with `Intent.PRIMARY`.

```tsx
// Blueprint ButtonGroup pattern — already used in project
<ButtonGroup>
  {MODES.map(({ key, label, shortcut }) => (
    <Button
      key={key}
      active={mapMode === key}
      intent={mapMode === key ? Intent.PRIMARY : Intent.NONE}
      onClick={() => setMapMode(key)}
      title={`${label} (${shortcut})`}
      small
    >
      {shortcut}: {label}
    </Button>
  ))}
</ButtonGroup>
```

### Pattern 10: CameraPresets

**What:** 4 preset camera positions — Theater Overview, Top-Down, Oblique, Free Camera. All use `viewer.camera.flyTo()`, which already appears in `CameraControls.tsx`.

```typescript
// Derived from CameraControls.tsx returnToGlobe() pattern
const CAMERA_PRESETS = {
  'THEATER_OVERVIEW': { pitch: -45, altitude_factor: 80000 },
  'TOP_DOWN':         { pitch: -90, altitude_factor: 100000 },
  'OBLIQUE':          { pitch: -25, altitude_factor: 50000 },
  'FREE':             null,  // disables trackedEntity, returns camera control to user
};
```

### Anti-Patterns to Avoid

- **Rebuilding all entities every 10Hz tick:** The Cesium entity API is slow for bulk updates. Use `GroundPrimitive` for coverage/threat/fusion polygons and update via `getGeometryInstanceAttributes()` color mutation (same as `useCesiumZones.ts`). Only swarm assignment lines use `viewer.entities` (few, slow-changing).
- **Attaching keyboard listeners outside useEffect:** Will not clean up on unmount, causing duplicate handlers.
- **Toggling Cesium viewer terrain exaggeration without guard:** Check `viewer.scene.globe.terrainExaggeration` exists before setting (Cesium 1.114 supports it but the terrain must be loaded first).
- **Using `viewer.entities` for heatmap-style coverage:** 20 UAVs × 10Hz = 200 entity mutations/sec. Use primitives.
- **Layer visibility driving entity add/remove:** Prefer `primitive.show = false` over removing/re-adding — removal triggers geometry re-upload on next show.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sensor coverage polygon | Custom geo math | `Cesium.EllipseGeometry` + `GroundPrimitive` | Handles globe curvature, depth testing, terrain clamp |
| Threat ring circle | Custom arc drawing | `Cesium.EllipseGeometry` with `semiMajorAxis`/`semiMinorAxis` | Same as above |
| Convex hull polygon | Hand-roll gift-wrap | Phase 7 `BattlespaceAssessor` provides `hull_points` directly | Already computed backend-side |
| Keyboard shortcut management | Event multiplexer | Single `window.addEventListener('keydown')` in one hook | KISS — no library needed |
| Heatmap coloring | d3-scale or chroma | Inline lerp function over 4 color stops | Zero dependency, 5 lines |

**Key insight:** Cesium 1.114 has everything needed. The temptation is to reach for deck.gl or Mapbox heatmaps — don't. This project is fully committed to Cesium and those libraries would fight the existing architecture.

---

## Common Pitfalls

### Pitfall 1: Layer show/hide vs add/remove

**What goes wrong:** Calling `viewer.scene.primitives.remove(p)` and re-adding it on each visibility toggle causes a GPU geometry re-upload each time, creating noticeable stutter.

**Why it happens:** `GroundPrimitive` uploads geometry to GPU on first render. Removing and re-creating triggers re-upload.

**How to avoid:** Set `primitive.show = false` when layer is hidden. Only add the primitive once on first data arrival. Check `primitiveRef.current` before adding.

**Warning signs:** Frame rate drops when toggling a layer that has many geometry instances (coverage layer with 20 UAVs).

### Pitfall 2: Keyboard events firing in text inputs

**What goes wrong:** User types "1" in a search or command input, triggering OPERATIONAL mode switch.

**Why it happens:** `keydown` on `window` fires regardless of focused element.

**How to avoid:** Guard: `if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;`

### Pitfall 3: Mode switch without layer visibility reset

**What goes wrong:** User toggles individual layers in COVERAGE mode, then switches to THREAT mode. The individually-toggled layers from COVERAGE remain visible, contaminating the THREAT view.

**Why it happens:** `setMapMode()` only sets `mapMode`, not `layerVisibility`.

**How to avoid:** `setMapMode()` must always replace `layerVisibility` with the mode's defaults (see Pattern 1 above). Individual `toggleLayer()` is additive on top of current visibility.

### Pitfall 4: Terrain exaggeration bleed

**What goes wrong:** Terrain mode sets `terrainExaggeration = 2.0`, user switches to another mode, and exaggeration stays at 2.0 making the globe look wrong.

**Why it happens:** Terrain layer hook only runs when its visibility changes, and cleanup resets exaggeration — but if cleanup isn't implemented, the mutation persists.

**How to avoid:** In `useTerrainLayer` effect cleanup (return function), reset `viewer.scene.globe.terrainExaggeration = 1.0`.

### Pitfall 5: Phase 7/5 data unavailable before those phases complete

**What goes wrong:** Phase 9 is executed before Phase 7 (battlespace) and Phase 5 (swarm). The `assessment` and `swarm_tasks` fields don't exist in the payload, causing null reference errors in threat and swarm layers.

**Why it happens:** Phase 9 depends on phases that are still PLANNED.

**How to avoid:** All layer hooks must null-check their data: `const clusters = state.assessment?.clusters ?? []`. Threat layer must degrade gracefully using only `target.threat_range_km` if no `assessment` data is present.

---

## Code Examples

### Zustand Store Extension

```typescript
// Add to SimulationStore.ts — immutable pattern
type MapMode = 'OPERATIONAL' | 'COVERAGE' | 'THREAT' | 'FUSION' | 'SWARM' | 'TERRAIN';

const MAP_MODE_DEFAULTS: Record<MapMode, Record<string, boolean>> = {
  OPERATIONAL: { drones: true, targets: true, zones: true, flows: true,
                 coverage: false, threat: false, fusion: false, swarm: false, terrain: false },
  COVERAGE:    { drones: true, targets: false, zones: true, flows: false,
                 coverage: true, threat: false, fusion: false, swarm: false, terrain: false },
  THREAT:      { drones: false, targets: true, zones: false, flows: false,
                 coverage: false, threat: true, fusion: false, swarm: false, terrain: false },
  FUSION:      { drones: true, targets: true, zones: false, flows: false,
                 coverage: false, threat: false, fusion: true, swarm: false, terrain: false },
  SWARM:       { drones: true, targets: true, zones: false, flows: true,
                 coverage: false, threat: false, fusion: false, swarm: true, terrain: false },
  TERRAIN:     { drones: true, targets: true, zones: false, flows: false,
                 coverage: false, threat: false, fusion: false, swarm: false, terrain: true },
};

// In SimState interface:
mapMode: MapMode;
layerVisibility: Record<string, boolean>;

// Actions:
setMapMode: (mode: MapMode) => void;
toggleLayer: (layer: string) => void;

// In create():
mapMode: 'OPERATIONAL',
layerVisibility: { ...MAP_MODE_DEFAULTS['OPERATIONAL'] },
setMapMode: (mode) => set({ mapMode: mode, layerVisibility: { ...MAP_MODE_DEFAULTS[mode] } }),
toggleLayer: (layer) => set((state) => ({
  layerVisibility: { ...state.layerVisibility, [layer]: !state.layerVisibility[layer] }
})),
```

### Coverage Layer — EllipseGeometry GroundPrimitive

```typescript
// Cesium pattern: EllipseGeometry instances in a GroundPrimitive
// Source: CesiumJS API docs + useCesiumZones.ts project pattern
function buildCoverageInstances(uavs: UAV[]): Cesium.GeometryInstance[] {
  return uavs.map((uav) => {
    const sensorColor = uav.sensors.includes('EO_IR')
      ? Cesium.Color.fromCssColorString('rgba(6, 182, 212, 0.15)')   // cyan
      : uav.sensors.includes('SAR')
      ? Cesium.Color.fromCssColorString('rgba(234, 179, 8, 0.15)')   // yellow
      : Cesium.Color.fromCssColorString('rgba(168, 85, 247, 0.15)'); // purple SIGINT

    return new Cesium.GeometryInstance({
      id: `coverage_${uav.id}`,
      geometry: new Cesium.EllipseGeometry({
        center: Cesium.Cartesian3.fromDegrees(uav.lon, uav.lat),
        semiMajorAxis: SENSOR_RANGE_KM * 1000,
        semiMinorAxis: SENSOR_RANGE_KM * 1000,
        height: 0,
      }),
      attributes: {
        color: Cesium.ColorGeometryInstanceAttribute.fromColor(sensorColor),
      },
    });
  });
}
```

### Camera Presets

```typescript
// Derived from CameraControls.tsx pattern
function flyToPreset(viewer: Cesium.Viewer, theater: TheaterInfo | null, preset: string) {
  const b = theater?.bounds;
  const lon = b ? (b.min_lon + b.max_lon) / 2 : 24.9668;
  const lat = b ? (b.min_lat + b.max_lat) / 2 : 41.2;

  const configs: Record<string, { altitude: number; pitch: number }> = {
    THEATER_OVERVIEW: { altitude: 500000, pitch: -45 },
    TOP_DOWN:         { altitude: 300000, pitch: -90 },
    OBLIQUE:          { altitude: 200000, pitch: -25 },
  };

  const cfg = configs[preset];
  if (!cfg) return;

  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(lon, lat, cfg.altitude),
    orientation: {
      heading: Cesium.Math.toRadians(0),
      pitch: Cesium.Math.toRadians(cfg.pitch),
      roll: 0.0,
    },
    duration: 1.5,
  });
}
```

### MapModeBar Placement

```tsx
// In CesiumContainer.tsx — position consistent with CameraControls (top-left)
// MapModeBar goes top-right, LayerPanel toggles below it
<ViewerContext.Provider value={viewerRef}>
  <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }} />
  <CameraControls />
  <MapModeBar />     {/* NEW — top-right absolute */}
  <LayerPanel />     {/* NEW — top-right below MapModeBar, collapsible */}
  <CameraPresets />  {/* NEW — bottom-right absolute */}
  <DroneCamPIP />
  {children}
</ViewerContext.Provider>
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| viewer.entities for all overlays | GroundPrimitive for polygon layers | Phase 0 patterns (useCesiumZones) | 10-50x fewer GPU draw calls for zone/coverage polygons |
| Global imageryLayer show/hide | Per-primitive `show` flag | Established pattern | Granular control without layer re-upload |

**Deprecated/outdated:**
- `viewer.imageryLayers.addImageryProvider` for dynamic overlays: Use `Primitive` objects for live data overlays, not imagery layers (which are static tile-based and not suitable for per-tick data).

---

## Open Questions

1. **Assessment data payload shape at Phase 9 execution time**
   - What we know: Phase 7 `BattlespaceAssessor` will add an `assessment` key to `get_state()` with `clusters`, `coverage_gaps`, `zone_scores`, `corridors`
   - What's unclear: Phase 9 may execute before Phase 7 is complete. Threat layer cluster polygons depend on `assessment.clusters`.
   - Recommendation: Threat layer reads `assessment?.clusters ?? []` and falls back to per-target `threat_range_km` rings which are already in the payload.

2. **Swarm layer formation data**
   - What we know: Phase 5 will add `swarm_tasks` to the payload; `tracked_target_ids` is already in UAV objects
   - What's unclear: `swarm_tasks` payload shape exact at Phase 9 execution time
   - Recommendation: Swarm layer uses `uav.tracked_target_ids` as fallback — this is already in the payload and sufficient for showing assignment lines.

3. **Layer toggle for "drones" and "targets" visibility**
   - What we know: Drone and target hooks (`useCesiumDrones`, `useCesiumTargets`) don't currently check a visibility flag
   - What's unclear: Should layer panel control drone/target Cesium entity visibility?
   - Recommendation: Add `layerVisibility.drones` / `layerVisibility.targets` flags and check them inside `useCesiumDrones` / `useCesiumTargets`. The hooks already subscribe to Zustand store — add one guard per update cycle.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, `src/python/tests/`) |
| Config file | `src/python/tests/conftest.py` (exists) |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/ -x -q` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/` |

Phase 9 is entirely frontend (TypeScript/React). No Python test additions required.

### Frontend Testing Note

No frontend test framework is currently installed (no vitest, jest, or test files outside node_modules). Phase 9 frontend validation is visual/manual — run the app and verify each mode visually. This is consistent with all prior frontend phases.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Command | File Exists? |
|--------|----------|-----------|---------|-------------|
| FR-8 | 6 map modes switchable via keyboard 1-6 | manual | Run app, press 1-6, verify mode label changes | N/A |
| FR-8 | Mode switch changes layer visibility | manual | Switch to THREAT, verify threat rings appear, drone icons hide | N/A |
| FR-8 | Individual layer toggles work | manual | In COVERAGE mode, uncheck "Coverage", verify circles disappear | N/A |
| FR-8 | Camera presets fly to correct views | manual | Click TOP_DOWN, verify camera pitch = -90 | N/A |
| NFR-1 | 60fps maintained with all layers active | manual | Enable all layers, verify no frame drop in browser devtools | N/A |

### Sampling Rate

- **Per task commit:** TypeScript compile check (`cd src/frontend-react && npx tsc --noEmit`)
- **Per wave merge:** Full Python test suite (`./venv/bin/python3 -m pytest src/python/tests/`)
- **Phase gate:** Visual UAT of all 6 modes before `/gsd:verify-work`

### Wave 0 Gaps

None for Python. Frontend has no automated test infrastructure — this is pre-existing and out of scope for Phase 9.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection: `src/frontend-react/src/cesium/useCesiumZones.ts` — GroundPrimitive + PerInstanceColorAppearance pattern
- Direct codebase inspection: `src/frontend-react/src/cesium/useCesiumRangeRings.ts` — viewer.entities ellipse pattern
- Direct codebase inspection: `src/frontend-react/src/cesium/CameraControls.tsx` — flyTo camera preset pattern
- Direct codebase inspection: `src/frontend-react/src/store/SimulationStore.ts` — Zustand 4.5.0 create() pattern
- Direct codebase inspection: `src/frontend-react/src/store/types.ts` — Target payload confirms threat_range_km, sensor_contributions present
- Direct codebase inspection: `src/python/sim_engine.py` get_state() — confirms no assessment/swarm data yet (phases not done)
- Direct codebase inspection: `src/frontend-react/package.json` — confirms cesium 1.114.0, blueprint 5.13.0, zustand 4.5.0

### Secondary (MEDIUM confidence)

- Phase 5 RESEARCH.md — confirms swarm layer data shape (swarm_tasks, tracked_target_ids)
- Phase 7 RESEARCH.md — confirms threat cluster hull_points shape from BattlespaceAssessor

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries confirmed by package.json inspection
- Architecture: HIGH — all patterns derived directly from existing codebase hooks
- Pitfalls: HIGH — identified from direct code reading of Cesium primitive lifecycle
- Phase dependencies: MEDIUM — Phase 5/7 payload shapes are planned but not yet implemented

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable stack, no fast-moving dependencies)
